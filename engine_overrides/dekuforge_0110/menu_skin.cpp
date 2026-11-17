// DekuForge's forest-glass interface. UI geometry only; no game renderer changes.
#include <algorithm>
#include <cmath>
#include <cstring>
#include "imgui.h"
#include "imgui_internal.h"
#include "ui/menu_art.h"
#include "ui/menu_skin.h"
#include "ui/deku_brand_pixels.h"

namespace {
int logo_rect = -1;
ImVec2 logo_uv0, logo_uv1;
bool logo_ready;
ImU32 color(int r, int g, int b, float a = 1) { return IM_COL32(r,g,b,(int)(255*std::clamp(a,0.0f,1.0f))); }
}

void skin_art_prepare(int, uint8_t *, uint32_t, uint32_t) {}
void skin_art_halve(const uint8_t *src, uint32_t w, uint32_t h, uint8_t *dst, uint32_t dw, uint32_t dh) {
    for (uint32_t y=0;y<dh;y++) for (uint32_t x=0;x<dw;x++) for (int c=0;c<4;c++) {
        unsigned sum=0;
        for (unsigned j=0;j<2;j++) for (unsigned i=0;i<2;i++)
            sum+=src[4*((size_t)std::min(y*2+j,h-1)*w+std::min(x*2+i,w-1))+c];
        dst[4*((size_t)y*dw+x)+c]=(uint8_t)((sum+2)/4);
    }
}

// Retained texture utility API for auxiliary pages. DekuForge's skin uses no game menu art.
extern "C" int menu_art_draw(ImDrawList *dl, MenuArt id, ImVec2 a, ImVec2 b, ImU32 tint) {
    ImTextureID tex; if (!menu_art(id,&tex,nullptr,nullptr)) return 0;
    dl->AddImage(tex,a,b,ImVec2(0,0),ImVec2(1,1),tint); return 1;
}
extern "C" int menu_art_draw9_turned(ImDrawList *dl, MenuArt id, ImVec2 a, ImVec2 b, float corner, float frac, ImU32 tint, int fill, int turned) {
    ImTextureID tex; if (!menu_art(id,&tex,nullptr,nullptr)) return 0;
    float c=std::min(corner,std::min((b.x-a.x)/2,(b.y-a.y)/2));
    float xs[]={a.x,a.x+c,b.x-c,b.x},ys[]={a.y,a.y+c,b.y-c,b.y};
    float uv[]={0,frac,1-frac,1};
    for(int y=0;y<3;y++) for(int x=0;x<3;x++) {
        if(x==1&&y==1&&!fill) continue;
        auto u=[&](int n){return turned?1-uv[n]:uv[n];};
        dl->AddImage(tex,ImVec2(xs[x],ys[y]),ImVec2(xs[x+1],ys[y+1]),ImVec2(u(x),u(y)),ImVec2(u(x+1),u(y+1)),tint);
    }
    return 1;
}
extern "C" int menu_art_draw9(ImDrawList *dl, MenuArt id, ImVec2 a, ImVec2 b, float c, float f, ImU32 tint, int fill) {
    return menu_art_draw9_turned(dl,id,a,b,c,f,tint,fill,0);
}

void skin_style(ImGuiStyle &s) {
    ImGui::StyleColorsDark(&s);
    s.WindowRounding=16; s.ChildRounding=12; s.FrameRounding=8; s.TabRounding=8; s.GrabRounding=6;
    s.WindowPadding=ImVec2(32,24); s.FramePadding=ImVec2(16,9); s.ItemSpacing=ImVec2(14,11);
    s.WindowBorderSize=0; s.FrameBorderSize=0; s.ScrollbarSize=12;
    auto *c=s.Colors;
    c[ImGuiCol_Text]=ImVec4(.91f,.95f,.89f,1);
    c[ImGuiCol_TextDisabled]=ImVec4(.52f,.65f,.55f,1);
    c[ImGuiCol_WindowBg]=ImVec4(.035f,.078f,.053f,.97f);
    c[ImGuiCol_PopupBg]=ImVec4(.055f,.115f,.075f,.99f);
    c[ImGuiCol_ChildBg]=ImVec4(0,0,0,0);
    c[ImGuiCol_Border]=ImVec4(.20f,.36f,.24f,.8f);
    c[ImGuiCol_FrameBg]=ImVec4(.075f,.15f,.10f,1);
    c[ImGuiCol_FrameBgHovered]=ImVec4(.13f,.25f,.15f,1);
    c[ImGuiCol_FrameBgActive]=ImVec4(.18f,.34f,.19f,1);
    c[ImGuiCol_Button]=c[ImGuiCol_FrameBg];
    c[ImGuiCol_ButtonHovered]=c[ImGuiCol_FrameBgHovered];
    c[ImGuiCol_ButtonActive]=c[ImGuiCol_FrameBgActive];
    c[ImGuiCol_Header]=c[ImGuiCol_FrameBg];
    c[ImGuiCol_HeaderHovered]=c[ImGuiCol_FrameBgHovered];
    c[ImGuiCol_HeaderActive]=c[ImGuiCol_FrameBgActive];
    c[ImGuiCol_Tab]=ImVec4(.065f,.13f,.085f,1);
    c[ImGuiCol_TabHovered]=ImVec4(.18f,.31f,.17f,1);
    c[ImGuiCol_TabSelected]=ImVec4(.20f,.36f,.17f,1);
    c[ImGuiCol_TabSelectedOverline]=ImVec4(.62f,.83f,.34f,1);
    c[ImGuiCol_CheckMark]=ImVec4(.68f,.87f,.40f,1);
    c[ImGuiCol_SliderGrab]=ImVec4(.40f,.65f,.31f,1);
    c[ImGuiCol_SliderGrabActive]=ImVec4(.71f,.90f,.43f,1);
    c[ImGuiCol_NavCursor]=ImVec4(.65f,.86f,.38f,1);
    c[ImGuiCol_Separator]=ImVec4(.20f,.32f,.23f,.7f);
    c[ImGuiCol_PlotLines]=ImVec4(.58f,.84f,.37f,1);
    c[ImGuiCol_ScrollbarBg]=ImVec4(.025f,.06f,.035f,.5f);
    c[ImGuiCol_ScrollbarGrab]=ImVec4(.18f,.30f,.20f,.9f);
    c[ImGuiCol_ScrollbarGrabHovered]=ImVec4(.31f,.47f,.27f,1);
}

void skin_atlas_add(ImFontAtlas *fa) { logo_rect=fa->AddCustomRectRegular(DEKU_BRAND_W,DEKU_BRAND_H); logo_ready=false; }
void skin_atlas_fill(ImFontAtlas *fa) {
    unsigned char *pixels; int w,h; fa->GetTexDataAsRGBA32(&pixels,&w,&h);
    auto *r=logo_rect>=0?fa->GetCustomRectByIndex(logo_rect):nullptr;
    if(!pixels||!r||!r->IsPacked()) return;
    for(int y=0;y<DEKU_BRAND_H;y++) std::memcpy(pixels+4*((size_t)(r->Y+y)*w+r->X),deku_brand_rgba+4*(size_t)y*DEKU_BRAND_W,4*DEKU_BRAND_W);
    fa->CalcCustomRectUV(r,&logo_uv0,&logo_uv1); logo_ready=true;
}
float skin_brand_height(float width) { return width*DEKU_BRAND_H/DEKU_BRAND_W; }
void skin_brand(ImDrawList *dl, ImVec2 at, float width) {
    if(logo_ready) dl->AddImage(ImGui::GetIO().Fonts->TexID,at,ImVec2(at.x+width,at.y+skin_brand_height(width)),logo_uv0,logo_uv1);
    else dl->AddText(at,SKIN_GOLD,"DekuForge");
}

void skin_panel(ImDrawList *dl, ImVec2 a, ImVec2 b, float s, float alpha) {
    dl->AddRectFilled(ImVec2(a.x+2*s,a.y+7*s),ImVec2(b.x+2*s,b.y+7*s),color(0,0,0,.25f*alpha),14*s);
    dl->AddRectFilled(a,b,color(9,23,15,.98f*alpha),14*s);
    dl->AddRect(a,b,color(64,100,65,.85f*alpha),14*s,0,1*s);
    dl->AddLine(ImVec2(a.x+18*s,a.y+1*s),ImVec2(b.x-18*s,a.y+1*s),color(135,177,83,.7f*alpha),1*s);
}
void skin_button(ImDrawList *dl, ImVec2 a, ImVec2 b, float s, float lift, bool dim) {
    float t=dim?.15f:std::clamp(lift,0.0f,1.0f);
    dl->AddRectFilled(a,b,color(25+(int)(20*t),47+(int)(33*t),31+(int)(13*t),dim?.55f:1),8*s);
    dl->AddRect(a,b,color(65+(int)(52*t),94+(int)(55*t),62,dim?.35f:.75f),8*s,0,1*s);
    if(t>.3f) dl->AddRectFilled(ImVec2(a.x+1*s,a.y+9*s),ImVec2(a.x+4*s,b.y-9*s),color(157,201,86,t),2*s);
}
float skin_cursor_reach(float s) { return 5*s; }
void skin_cursor_glow(ImDrawList *dl, ImVec2 a, ImVec2 b, float s, float alpha) {
    dl->AddRect(ImVec2(a.x-3*s,a.y-3*s),ImVec2(b.x+3*s,b.y+3*s),color(137,195,83,.16f*alpha),11*s,0,4*s);
}
void skin_cursor_frame(ImDrawList *dl, ImVec2 a, ImVec2 b, float s, float alpha) {
    dl->AddRect(ImVec2(a.x-1*s,a.y-1*s),ImVec2(b.x+1*s,b.y+1*s),color(171,220,105,.95f*alpha),9*s,0,1.4f*s);
}
float skin_filigree_height(float s) { return 19*s; }
void skin_filigree(ImDrawList *dl,float x0,float x1,float y,float s,float alpha) {
    dl->AddLine(ImVec2(x0,y),ImVec2(x1,y),color(65,98,67,.55f*alpha),s);
    dl->AddLine(ImVec2(x0,y),ImVec2(x0+std::min(48*s,(x1-x0)*.18f),y),color(174,203,99,.85f*alpha),2*s);
}
bool skin_widget_button(const char *label,ImVec2 size,float s) {
    ImVec2 text=ImGui::CalcTextSize(label,nullptr,true); auto &style=ImGui::GetStyle();
    ImVec2 extent(size.x>0?size.x:text.x+2*style.FramePadding.x,size.y>0?size.y:text.y+2*style.FramePadding.y);
    ImVec2 a=ImGui::GetCursorScreenPos(),b(a.x+extent.x,a.y+extent.y);
    bool pressed=ImGui::InvisibleButton(label,extent,ImGuiButtonFlags_EnableNav);
    bool focus=ImGui::IsItemFocused()&&ImGui::GetCurrentContext()->NavCursorVisible,hover=ImGui::IsItemHovered();
    auto *dl=ImGui::GetWindowDrawList();
    skin_button(dl,a,b,s,focus?1:hover?.7f:.1f,false);
    if(focus||hover) skin_cursor_frame(dl,a,b,s,focus?1:.65f);
    dl->AddText(ImVec2(a.x+(extent.x-text.x)/2,a.y+(extent.y-text.y)/2),SKIN_TEXT,label,ImGui::FindRenderedTextEnd(label));
    return pressed;
}
bool skin_tab_item(const char *id,const char *,int flags,float,ImFont *font) {
    if(font) ImGui::PushFont(font);
    bool result=ImGui::BeginTabItem(id,nullptr,flags);
    if(font) ImGui::PopFont();
    return result;
}
void skin_boot_panel(ImDrawList *dl,ImFont *head,float head_px,ImFont *body,float body_px,const char *title,const char *step,float frac,float sweep,float w,float h,float s) {
    float pw=std::min(740*s,w-32*s),ph=300*s;
    ImVec2 a((w-pw)/2,(h-ph)*.58f),b(a.x+pw,a.y+ph);
    dl->AddRectFilled(ImVec2(0,0),ImVec2(w,h),color(4,13,8));
    skin_panel(dl,a,b,s);
    float logo_w=240*s;skin_brand(dl,ImVec2((w-logo_w)/2,a.y+18*s),logo_w);
    float y=a.y+145*s;
    dl->AddText(head,head_px,ImVec2(a.x+32*s,y),SKIN_GOLD,title);
    y+=head_px+16*s;
    dl->AddText(body,body_px,ImVec2(a.x+32*s,y),SKIN_TEXT,step);
    y+=body_px+22*s;
    ImVec2 bar(a.x+32*s,y),end(b.x-32*s,y+8*s);
    dl->AddRectFilled(bar,end,color(23,45,28),4*s);
    float length=end.x-bar.x;
    float x=frac>=0?bar.x:bar.x+length*.75f*std::clamp(sweep,0.0f,1.0f);
    float to=frac>=0?bar.x+length*std::clamp(frac,0.0f,1.0f):x+length*.25f;
    dl->AddRectFilled(ImVec2(x,y),ImVec2(to,end.y),color(164,205,91),4*s);
}
