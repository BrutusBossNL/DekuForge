// Standalone per-user setup. Embeds only the verified launcher package and installer script.
#define UNICODE 1
#define _UNICODE 1
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <stdio.h>
#include <wchar.h>

static HINSTANCE app;
static HWND path_edit, status_text, install_button, tools_check;
static PROCESS_INFORMATION child;
static wchar_t work[32768], log_path[32768];
static int silent_mode, no_launch, skip_tools, no_shortcut;
static HBRUSH background;

static int resource_file(int id,const wchar_t *name) {
    HRSRC resource=FindResourceW(app,MAKEINTRESOURCEW(id),RT_RCDATA);
    if(!resource) return 0;
    HGLOBAL loaded=LoadResource(app,resource);
    DWORD size=SizeofResource(app,resource),written=0;
    HANDLE file=CreateFileW(name,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE) return 0;
    int ok=WriteFile(file,LockResource(loaded),size,&written,NULL)&&written==size;
    CloseHandle(file);return ok;
}

static void start_install(HWND window) {
    wchar_t root[32768],temp[32768],payload[32768],script[32768],shell[32768],command[32768];
    GetWindowTextW(path_edit,root,32768);
    if(!root[0]) return;
    if(!GetTempPathW(32768,temp)) return;
    swprintf(work,32768,L"%lsDekuForge-setup-%lu-%llu",temp,GetCurrentProcessId(),GetTickCount64());
    if(!CreateDirectoryW(work,NULL)) return;
    swprintf(payload,32768,L"%ls\\launcher.zip",work);
    swprintf(script,32768,L"%ls\\install.ps1",work);
    swprintf(log_path,32768,L"%ls\\setup.log",work);
    if(!resource_file(102,payload)||!resource_file(103,script)) return;
    GetSystemDirectoryW(shell,32768);wcscat(shell,L"\\WindowsPowerShell\\v1.0\\powershell.exe");
    skip_tools=skip_tools||SendMessageW(tools_check,BM_GETCHECK,0,0)!=BST_CHECKED;
    int count=swprintf(command,32768,L"\"%ls\" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File \"%ls\" -Payload \"%ls\" -Root \"%ls\"%ls%ls%ls",
        shell,script,payload,root,no_launch?L" -NoLaunch":L"",skip_tools?L" -SkipTools":L"",no_shortcut?L" -NoShortcut":L"");
    if(count<0) return;
    SECURITY_ATTRIBUTES security={sizeof security,NULL,TRUE};
    HANDLE log=CreateFileW(log_path,GENERIC_WRITE,FILE_SHARE_READ,&security,CREATE_ALWAYS,FILE_ATTRIBUTE_NORMAL,NULL);
    STARTUPINFOW startup={0};startup.cb=sizeof startup;startup.dwFlags=STARTF_USESTDHANDLES;
    startup.hStdOutput=log;startup.hStdError=log;
    startup.hStdInput=CreateFileW(L"NUL",GENERIC_READ,FILE_SHARE_READ|FILE_SHARE_WRITE,&security,OPEN_EXISTING,0,NULL);
    BOOL ok=CreateProcessW(shell,command,NULL,NULL,TRUE,CREATE_NO_WINDOW,NULL,work,&startup,&child);
    CloseHandle(log);CloseHandle(startup.hStdInput);
    if(!ok) { MessageBoxW(window,L"Could not start setup.",L"DekuForge",MB_ICONERROR);return; }
    EnableWindow(install_button,FALSE);EnableWindow(path_edit,FALSE);EnableWindow(tools_check,FALSE);
    SetWindowTextW(status_text,L"Installing and preparing tools. This can take several minutes...\nThe game is built later from your own files.");
    SetTimer(window,1,250,NULL);
}

static LRESULT CALLBACK window_proc(HWND w,UINT msg,WPARAM wp,LPARAM lp) {
    if(msg==WM_COMMAND && LOWORD(wp)==2) {
        BROWSEINFOW browse={0};browse.hwndOwner=w;browse.lpszTitle=L"Where should DekuForge be installed?";
        browse.ulFlags=BIF_RETURNONLYFSDIRS|BIF_NEWDIALOGSTYLE;
        PIDLIST_ABSOLUTE chosen=SHBrowseForFolderW(&browse);
        if(chosen) { wchar_t folder[MAX_PATH];if(SHGetPathFromIDListW(chosen,folder)) SetWindowTextW(path_edit,folder);CoTaskMemFree(chosen); }
        return 0;
    }
    if(msg==WM_COMMAND && LOWORD(wp)==1) { start_install(w);return 0; }
    if(msg==WM_TIMER && child.hProcess && WaitForSingleObject(child.hProcess,0)!=WAIT_TIMEOUT) {
        DWORD code=1;GetExitCodeProcess(child.hProcess,&code);KillTimer(w,1);
        CloseHandle(child.hThread);CloseHandle(child.hProcess);child.hProcess=NULL;
        if(!code) {
            SetWindowTextW(status_text,L"DekuForge is installed. Use DekuForge.exe or the Start Menu shortcut.");
            if(!silent_mode) MessageBoxW(w,L"DekuForge is ready. Choose Build game and select your own NUP archive.",L"DekuForge",MB_OK|MB_ICONINFORMATION);
            DestroyWindow(w);PostQuitMessage(0);
        } else {
            wchar_t message[32768];swprintf(message,32768,L"Setup stopped. Your game files and saves were not removed.\nLog: %ls",log_path);
            SetWindowTextW(status_text,message);
            if(silent_mode) {DestroyWindow(w);PostQuitMessage(1);} else EnableWindow(install_button,TRUE);
        }
        return 0;
    }
    if(msg==WM_CLOSE) {
        if(child.hProcess) {MessageBoxW(w,L"Setup is active. Please wait for it to finish.",L"DekuForge",MB_OK);return 0;}
        DestroyWindow(w);PostQuitMessage(0);return 0;
    }
    if(msg==WM_CTLCOLORSTATIC || msg==WM_CTLCOLOREDIT) {SetTextColor((HDC)wp,RGB(231,242,225));SetBkColor((HDC)wp,RGB(12,30,19));return (LRESULT)background;}
    return DefWindowProcW(w,msg,wp,lp);
}

int WINAPI wWinMain(HINSTANCE instance,HINSTANCE previous,PWSTR args,int show) {
    (void)previous;(void)args;(void)show;app=instance;CoInitializeEx(NULL,COINIT_APARTMENTTHREADED);
    background=CreateSolidBrush(RGB(12,30,19));
    wchar_t initial[32768];SHGetFolderPathW(NULL,CSIDL_LOCAL_APPDATA,NULL,0,initial);wcscat(initial,L"\\Programs\\DekuForge Preview");
    int argc;wchar_t **argv=CommandLineToArgvW(GetCommandLineW(),&argc);
    for(int i=1;i<argc;i++) {
        if(!_wcsicmp(argv[i],L"/SILENT")) silent_mode=1;
        else if(!_wcsicmp(argv[i],L"/NOLAUNCH")) no_launch=1;
        else if(!_wcsicmp(argv[i],L"/NOSHORTCUT")) no_shortcut=1;
        else if(!_wcsicmp(argv[i],L"/SKIPTOOLS")) skip_tools=1;
        else if(!_wcsnicmp(argv[i],L"/DIR=",5)) wcsncpy(initial,argv[i]+5,32767);
    }
    LocalFree(argv);
    WNDCLASSW wc={0};wc.lpfnWndProc=window_proc;wc.hInstance=instance;wc.lpszClassName=L"DekuForgeSetup";
    wc.hbrBackground=background;wc.hCursor=LoadCursorW(NULL,IDC_ARROW);wc.hIcon=LoadIconW(instance,MAKEINTRESOURCEW(101));RegisterClassW(&wc);
    HWND w=CreateWindowW(wc.lpszClassName,L"DekuForge Setup",WS_OVERLAPPED|WS_CAPTION|WS_SYSMENU|WS_MINIMIZEBOX,
        (GetSystemMetrics(SM_CXSCREEN)-650)/2,(GetSystemMetrics(SM_CYSCREEN)-350)/2,650,350,NULL,NULL,instance,NULL);
    HFONT font=CreateFontW(-17,0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
    CreateWindowW(L"STATIC",L"DekuForge - Reforging a legend.",WS_CHILD|WS_VISIBLE,26,22,580,30,w,NULL,instance,NULL);
    CreateWindowW(L"STATIC",L"Where should DekuForge be installed?",WS_CHILD|WS_VISIBLE,26,70,580,26,w,NULL,instance,NULL);
    path_edit=CreateWindowExW(WS_EX_CLIENTEDGE,L"EDIT",initial,WS_CHILD|WS_VISIBLE|ES_AUTOHSCROLL,26,101,470,30,w,NULL,instance,NULL);
    CreateWindowW(L"BUTTON",L"Browse...",WS_CHILD|WS_VISIBLE,509,101,108,30,w,(HMENU)2,instance,NULL);
    tools_check=CreateWindowW(L"BUTTON",L"Download and prepare game build tools now",WS_CHILD|WS_VISIBLE|BS_AUTOCHECKBOX,26,146,580,26,w,NULL,instance,NULL);
    SendMessageW(tools_check,BM_SETCHECK,skip_tools?BST_UNCHECKED:BST_CHECKED,0);
    status_text=CreateWindowW(L"STATIC",L"No game files are included. You need your own supported game dump.",WS_CHILD|WS_VISIBLE,26,190,580,60,w,NULL,instance,NULL);
    install_button=CreateWindowW(L"BUTTON",L"Install DekuForge",WS_CHILD|WS_VISIBLE|BS_DEFPUSHBUTTON,420,267,197,32,w,(HMENU)1,instance,NULL);
    for(HWND control=GetWindow(w,GW_CHILD);control;control=GetWindow(control,GW_HWNDNEXT)) SendMessageW(control,WM_SETFONT,(WPARAM)font,TRUE);
    if(silent_mode) start_install(w);else ShowWindow(w,SW_SHOW);
    MSG event;while(GetMessageW(&event,NULL,0,0)>0) {TranslateMessage(&event);DispatchMessageW(&event);}
    DeleteObject(font);DeleteObject(background);CoUninitialize();return (int)event.wParam;
}
