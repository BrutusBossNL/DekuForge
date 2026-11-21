// Portable checks for bsdtar listings. No Windows API: unit tests compile this
// file on any host with synthetic listings.
#include "archive_check.h"
#include <stdlib.h>
#include <string.h>

typedef struct { const char *text; size_t length; } line;

static int next_line(const char *data, size_t length, size_t *offset, line *out) {
    while (*offset < length) {
        size_t start = *offset, end = start;
        while (end < length && data[end] != '\n') ++end;
        *offset = end < length ? end + 1 : end;
        size_t trimmed = end;
        if (trimmed > start && data[trimmed - 1] == '\r') --trimmed;
        if (trimmed == start) {
            if (*offset >= length) return 0;  // Only a final empty line is accepted.
            out->text = NULL; out->length = 0;
            return -1;
        }
        out->text = data + start; out->length = trimmed - start;
        return 1;
    }
    return 0;
}

static char lower(char c) { return c >= 'A' && c <= 'Z' ? (char)(c - 'A' + 'a') : c; }

static int reserved_component(const char *text, size_t length) {
    static const char *names[] = {"con", "prn", "aux", "nul"};
    size_t stem = 0;
    while (stem < length && text[stem] != '.') ++stem;
    while (stem && text[stem - 1] == ' ') --stem;
    char value[5] = {0};
    if (stem < 3 || stem > 4) return 0;
    for (size_t i = 0; i < stem; ++i) value[i] = lower(text[i]);
    for (size_t i = 0; i < sizeof names / sizeof names[0]; ++i) if (!strcmp(value, names[i])) return 1;
    return stem == 4 && (!strncmp(value, "com", 3) || !strncmp(value, "lpt", 3)) && value[3] >= '0' && value[3] <= '9';
}

static const char *check_name(const line *entry, const deku_listing_rules *rules) {
    const char *name = entry->text;
    size_t length = entry->length;
    if (!length || name[0] == '/') return "Archive member uses an absolute path";
    if (rules->required_prefix) {
        size_t prefix = strlen(rules->required_prefix);
        if (length < prefix || memcmp(name, rules->required_prefix, prefix)) return "Archive member outside the expected folder";
    }
    for (size_t i = 0; i < length; ++i) {
        unsigned char c = (unsigned char)name[i];
        if (c < 0x20 || c > 0x7e) return "Archive member name is not plain ASCII";
        if (c == '\\' || c == ':' || c == '<' || c == '>' || c == '"' || c == '|' || c == '?' || c == '*')
            return "Archive member name contains a reserved character";
    }
    size_t start = 0;
    size_t body = name[length - 1] == '/' ? length - 1 : length;
    if (!body) return "Archive member uses an empty path";
    while (start <= body) {
        size_t end = start;
        while (end < body && name[end] != '/') ++end;
        size_t part = end - start;
        if (!part) return "Archive member has an empty path component";
        if ((part == 1 && name[start] == '.') || (part == 2 && name[start] == '.' && name[start + 1] == '.'))
            return "Archive member traverses directories";
        if (name[end - 1] == '.' || name[end - 1] == ' ') return "Archive member ends with a dot or space";
        if (reserved_component(name + start, part)) return "Archive member uses a reserved Windows name";
        start = end + 1;
    }
    return NULL;
}

static int parse_number(const char **cursor, const char *end, unsigned long long *value) {
    const char *p = *cursor;
    unsigned long long result = 0;
    if (p >= end || *p < '0' || *p > '9') return 0;
    while (p < end && *p >= '0' && *p <= '9') {
        unsigned digit = (unsigned)(*p - '0');
        if (result > (~0ULL - digit) / 10) return 0;
        result = result * 10 + digit; ++p;
    }
    *cursor = p; *value = result;
    return 1;
}

static int skip_token(const char **cursor, const char *end) {
    const char *p = *cursor;
    if (p >= end || *p == ' ' || *p == '\t') return 0;
    while (p < end && *p != ' ' && *p != '\t') ++p;
    *cursor = p;
    return 1;
}

static int skip_space(const char **cursor, const char *end) {
    const char *p = *cursor;
    if (p >= end || (*p != ' ' && *p != '\t')) return 0;
    while (p < end && (*p == ' ' || *p == '\t')) ++p;
    *cursor = p;
    return 1;
}

// bsdtar -tv: mode links owner group size date name. Only '-' and 'd' types;
// symbolic links ('l'), hard links ('h') and devices are refused.
static const char *check_detail(const line *entry, unsigned long long *size) {
    const char *p = entry->text, *end = entry->text + entry->length;
    unsigned long long links = 0;
    if (p >= end || (*p != '-' && *p != 'd')) return "Archive links or special files are refused";
    if (!skip_token(&p, end) || !skip_space(&p, end) || !parse_number(&p, end, &links) || !skip_space(&p, end)
        || !skip_token(&p, end) || !skip_space(&p, end) || !skip_token(&p, end) || !skip_space(&p, end)
        || !parse_number(&p, end, size) || !skip_space(&p, end))
        return "Archive listing has an unexpected format";
    return NULL;
}

static int compare_keys(const void *left, const void *right) {
    return strcmp(*(char *const *)left, *(char *const *)right);
}

const char *deku_check_listing(const char *names, size_t names_length,
                               const char *details, size_t details_length,
                               const deku_listing_rules *rules) {
    size_t count = 0, offset = 0;
    line entry;
    int state;
    while ((state = next_line(names, names_length, &offset, &entry)) != 0) {
        if (state < 0) return "Archive listing contains an empty member name";
        if (++count > rules->max_entries) return "Archive has too many members";
    }
    if (!count) return "Archive is empty";
    char **keys = calloc(count, sizeof *keys);
    if (!keys) return "Not enough memory to check the archive";
    const char *error = NULL;
    size_t index = 0;
    offset = 0;
    while (!error && next_line(names, names_length, &offset, &entry) > 0) {
        error = check_name(&entry, rules);
        if (error) break;
        size_t length = entry.length;
        if (entry.text[length - 1] == '/') --length;
        keys[index] = malloc(length + 1);
        if (!keys[index]) { error = "Not enough memory to check the archive"; break; }
        for (size_t i = 0; i < length; ++i) keys[index][i] = lower(entry.text[i]);
        keys[index++][length] = 0;
    }
    if (!error) {
        qsort(keys, count, sizeof *keys, compare_keys);
        for (size_t i = 1; i < count && !error; ++i)
            if (!strcmp(keys[i - 1], keys[i])) error = "Archive contains duplicate or case-colliding members";
    }
    if (!error) {
        size_t lines = 0;
        unsigned long long expanded = 0;
        offset = 0;
        while (!error && (state = next_line(details, details_length, &offset, &entry)) != 0) {
            unsigned long long size = 0;
            if (state < 0) { error = "Archive listing has an unexpected format"; break; }
            error = check_detail(&entry, &size);
            if (!error && (size > rules->max_expanded || expanded > rules->max_expanded - size))
                error = "Archive expands beyond its limit";
            expanded += size;
            ++lines;
        }
        if (!error && lines != count) error = "Archive listings disagree";
    }
    for (size_t i = 0; i < count; ++i) free(keys[i]);
    free(keys);
    return error;
}
