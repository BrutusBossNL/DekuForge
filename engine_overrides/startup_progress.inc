// Window-thread-only painting before the guest submits its first frame.
// Values cross threads through a synchronous window message, not shared strings.
#define DF_STARTUP_MESSAGE (WM_APP + 74)
static struct { unsigned stage, done, total; } df_startup;

void df_startup_progress(unsigned stage, unsigned done, unsigned total) {
    unsigned values[3] = {stage, done, total};
    if (g_hwnd) SendMessageW(g_hwnd, DF_STARTUP_MESSAGE, 0, (LPARAM)values);
}

static void df_startup_paint(HWND window) {
    PAINTSTRUCT paint;
    HDC dc = BeginPaint(window, &paint);
    RECT bounds;
    GetClientRect(window, &bounds);
    HBRUSH background = CreateSolidBrush(RGB(8, 22, 15));
    FillRect(dc, &bounds, background);
    DeleteObject(background);
    int width = bounds.right, height = bounds.bottom;
    int panel = width > 760 ? 680 : width - 48;
    if (panel < 1) panel = 1;
    int left = (width-panel)/2, top = height/2 - 60;
    HFONT font = CreateFontW(-28, 0, 0, 0, FW_SEMIBOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
        DEFAULT_PITCH, L"Segoe UI");
    HGDIOBJ old = SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(233, 187, 75));
    RECT title = {left, top, left+panel, top+42};
    DrawTextW(dc, L"DekuForge", -1, &title, DT_CENTER | DT_SINGLELINE);
    wchar_t label[160];
    const wchar_t *phase = df_startup.stage == 2 ? L"Preparing pipelines" :
        df_startup.stage == 3 ? L"Preparing compute shaders" : L"Preparing shaders";
    if (df_startup.total)
        swprintf(label, 160, L"%ls: %u / %u", phase, df_startup.done, df_startup.total);
    else swprintf(label, 160, L"%ls...", phase);
    RECT detail = {left, top+50, left+panel, top+94};
    SetTextColor(dc, RGB(235, 230, 203));
    DrawTextW(dc, label, -1, &detail, DT_CENTER | DT_SINGLELINE);
    RECT track = {left, top+110, left+panel, top+122};
    HBRUSH dark = CreateSolidBrush(RGB(48, 70, 40));
    FillRect(dc, &track, dark);
    DeleteObject(dark);
    if (df_startup.total) {
        unsigned done = df_startup.done > df_startup.total ? df_startup.total : df_startup.done;
        track.right = left + (int)((uint64_t)panel * done / df_startup.total);
        HBRUSH gold = CreateSolidBrush(RGB(233, 187, 75));
        FillRect(dc, &track, gold);
        DeleteObject(gold);
    }
    SelectObject(dc, old);
    DeleteObject(font);
    EndPaint(window, &paint);
}
