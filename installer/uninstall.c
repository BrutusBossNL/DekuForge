// The standalone bootstrap exits before its PowerShell helper removes the installation.
#define UNICODE 1
#define _UNICODE 1
#include <windows.h>
#include <stdio.h>
#include <wchar.h>

int WINAPI wWinMain(HINSTANCE app,HINSTANCE previous,PWSTR args,int show) {
    (void)previous;(void)show;
    wchar_t root[32768],temp[32768],script[32768],shell[32768],command[32768];
    if(!GetModuleFileNameW(NULL,root,32768)) return 1;
    wchar_t *slash=wcsrchr(root,L'\\');if(!slash)return 1;*slash=0;
    if(!GetTempPathW(32768,temp))return 1;
    swprintf(script,32768,L"%lsDekuForge-uninstall-%lu-%llu.ps1",temp,GetCurrentProcessId(),GetTickCount64());
    HRSRC resource=FindResourceW(app,MAKEINTRESOURCEW(103),RT_RCDATA);if(!resource)return 1;
    HGLOBAL loaded=LoadResource(app,resource);DWORD size=SizeofResource(app,resource),written;
    HANDLE file=CreateFileW(script,GENERIC_WRITE,0,NULL,CREATE_NEW,FILE_ATTRIBUTE_NORMAL,NULL);
    if(file==INVALID_HANDLE_VALUE)return 1;
    BOOL ok=WriteFile(file,LockResource(loaded),size,&written,NULL)&&written==size;CloseHandle(file);if(!ok)return 1;
    GetSystemDirectoryW(shell,32768);wcscat(shell,L"\\WindowsPowerShell\\v1.0\\powershell.exe");
    if(swprintf(command,32768,L"\"%ls\" -NoProfile -STA -ExecutionPolicy Bypass -File \"%ls\" -Root \"%ls\" %ls",shell,script,root,args)<0)return 1;
    STARTUPINFOW start={0};start.cb=sizeof start;PROCESS_INFORMATION child={0};
    if(!CreateProcessW(shell,command,NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,NULL,&start,&child))return 1;
    CloseHandle(child.hThread);CloseHandle(child.hProcess);return 0;
}
