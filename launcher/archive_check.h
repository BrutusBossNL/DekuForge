// Portable validation of `tar -tf` / `tar -tvf` listings before extraction.
#ifndef DEKUFORGE_ARCHIVE_CHECK_H
#define DEKUFORGE_ARCHIVE_CHECK_H
#include <stddef.h>

typedef struct {
    size_t max_entries;
    unsigned long long max_expanded;
    const char *required_prefix; // NULL when members may use any safe relative path.
} deku_listing_rules;

// Returns NULL when every member is a safe, unique regular file or directory
// within the bounds, otherwise a static English reason.
const char *deku_check_listing(const char *names, size_t names_length,
                               const char *details, size_t details_length,
                               const deku_listing_rules *rules);

#endif
