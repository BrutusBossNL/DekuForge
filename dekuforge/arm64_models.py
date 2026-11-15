"""Bit-exact reference models for instruction extensions awaiting native validation."""


def decode_half_negate(word):
    if word & 0xBFFFFC00 != 0x2EF8F800:
        return None
    return word & 31, (word >> 5) & 31, bool(word & (1 << 30))


def decode_byte_dot(word):
    if word & 0x9FE0FC00 != 0x0E809400:
        return None
    return word & 31, (word >> 5) & 31, (word >> 16) & 31, bool(word & (1 << 30)), bool(word & (1 << 29))


def negate_half_vector(value, wide):
    if not isinstance(value, int) or not 0 <= value < 1 << 128:
        raise ValueError("Expected unsigned 128-bit vector bits")
    lanes = 8 if wide else 4
    result = 0
    for lane in range(lanes):
        half = (value >> (16 * lane)) & 0xFFFF
        result |= (half ^ 0x8000) << (16 * lane)
    return result
