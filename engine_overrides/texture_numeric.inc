// Numeric bits occupy the unused high bits of the cached texture-type answer.
// Keep the lower six bits compatible with GFX_TEX_* and the answer file ABI.
static uint8_t df_texture_numeric(VkFormat format) {
    switch (format) {
    case VK_FORMAT_R8_UINT: case VK_FORMAT_R8G8_UINT: case VK_FORMAT_R8G8B8A8_UINT:
    case VK_FORMAT_R16_UINT: case VK_FORMAT_R16G16_UINT: case VK_FORMAT_R16G16B16A16_UINT:
    case VK_FORMAT_R32_UINT: case VK_FORMAT_R32G32_UINT: case VK_FORMAT_R32G32B32A32_UINT:
    case VK_FORMAT_A2B10G10R10_UINT_PACK32: return 128;
    case VK_FORMAT_R8_SINT: case VK_FORMAT_R8G8_SINT: case VK_FORMAT_R8G8B8A8_SINT:
    case VK_FORMAT_R16_SINT: case VK_FORMAT_R16G16_SINT: case VK_FORMAT_R16G16B16A16_SINT:
    case VK_FORMAT_R32_SINT: case VK_FORMAT_R32G32_SINT: case VK_FORMAT_R32G32B32A32_SINT:
    case VK_FORMAT_A2B10G10R10_SINT_PACK32: return 64;
    default: return 0;
    }
}

// Storage format codes match GfxShaderAnswers.img_format.
static uint8_t df_storage_format(VkFormat format) {
    switch (format) {
    case VK_FORMAT_R8_UNORM: return 1;
    case VK_FORMAT_R8_SNORM: return 2;
    case VK_FORMAT_R8_UINT: return 3;
    case VK_FORMAT_R8_SINT: return 4;
    case VK_FORMAT_R16_SFLOAT: return 5;
    case VK_FORMAT_R16_UNORM: return 6;
    case VK_FORMAT_R16_SNORM: return 7;
    case VK_FORMAT_R16_UINT: return 8;
    case VK_FORMAT_R16_SINT: return 9;
    case VK_FORMAT_R32_SFLOAT: return 10;
    case VK_FORMAT_R32_UINT: return 11;
    case VK_FORMAT_R32_SINT: return 12;
    case VK_FORMAT_R8G8_UNORM: return 13;
    case VK_FORMAT_R8G8_SNORM: return 14;
    case VK_FORMAT_R8G8_UINT: return 15;
    case VK_FORMAT_R8G8_SINT: return 16;
    case VK_FORMAT_R16G16_SFLOAT: return 17;
    case VK_FORMAT_R16G16_UNORM: return 18;
    case VK_FORMAT_R16G16_SNORM: return 19;
    case VK_FORMAT_R16G16_UINT: return 20;
    case VK_FORMAT_R16G16_SINT: return 21;
    case VK_FORMAT_R32G32_SFLOAT: return 22;
    case VK_FORMAT_R32G32_UINT: return 23;
    case VK_FORMAT_R32G32_SINT: return 24;
    case VK_FORMAT_R8G8B8A8_UNORM: return 25;
    case VK_FORMAT_R8G8B8A8_SNORM: return 26;
    case VK_FORMAT_R8G8B8A8_UINT: return 27;
    case VK_FORMAT_R8G8B8A8_SINT: return 28;
    case VK_FORMAT_R16G16B16A16_SFLOAT: return 29;
    case VK_FORMAT_R16G16B16A16_UNORM: return 30;
    case VK_FORMAT_R16G16B16A16_SNORM: return 31;
    case VK_FORMAT_R16G16B16A16_UINT: return 32;
    case VK_FORMAT_R16G16B16A16_SINT: return 33;
    case VK_FORMAT_R32G32B32A32_SFLOAT: return 34;
    case VK_FORMAT_R32G32B32A32_UINT: return 35;
    case VK_FORMAT_R32G32B32A32_SINT: return 36;
    case VK_FORMAT_A2B10G10R10_UNORM_PACK32: return 37;
    case VK_FORMAT_A2B10G10R10_UINT_PACK32: return 38;
    case VK_FORMAT_B10G11R11_UFLOAT_PACK32: return 39;
    default: return 0;
    }
}
