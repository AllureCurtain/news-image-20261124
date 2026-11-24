#!/usr/bin/env python3
"""Sum up 24 November 2026's world news in one 1024x1024 picture.

A front page drawn from scratch with the Python standard library only
(no Pillow, no network, no files read at runtime): a tiny software
canvas, a bitmap font embedded below (DejaVu Sans glyphs rendered to
1-bit bitmaps at 64 px by tools/make_font.py), and a PNG encoder built
on zlib. The program is fully deterministic: the same run twice writes
byte-identical output.

Run:  python3 main.py            (writes /output/entry.png)
       MAKEFUN_OUTPUT_DIR=out python3 main.py   (local test)

The news, researched on 24 November 2026:
  * COP31 in Antalya collapses with no deal -- the longest climate
    summit ever, killed by the fossil-fuel wording (lead story).
  * Nvidia reinstates Jensen Huang as CEO after 11 days; shares jump
    ~31%, about $1 trillion of value returns, Nasdaq +6%.
  * A candy-factory fire in Indonesia kills at least 24; ~30 missing.
  * Ukraine says it sank a Russian warship off Libya; Russian strikes
    hit the Kyiv region, killing several people.
  * The UN's top court rules Myanmar committed genocide against the
    Rohingya.
  * Sport: Alcaraz wins a maiden ATP Finals title in Turin; Gukesh
    begins his world chess title defence in Geneva.
"""
import base64
import math
import os
import struct
import zlib

W = 1024
H = 1024

# --- palette -------------------------------------------------------------
PAPER = (247, 243, 234)
INK = (20, 32, 46)
NAVY = (14, 42, 71)
NAVY_DARK = (9, 28, 48)
GOLD = (201, 162, 39)
GOLD_LIGHT = (232, 197, 92)
RED = (178, 35, 24)
RED_DARK = (140, 24, 16)
CARD = (255, 255, 255)
CARD_LINE = (216, 210, 196)
BODY = (74, 85, 104)
GREEN_DARK = (18, 59, 42)
GREEN_LINE = (126, 208, 126)
OCEAN = (38, 110, 168)
OCEAN_DEEP = (24, 78, 128)
LAND = (86, 158, 94)
LAND_DARK = (62, 128, 74)
SKY = (214, 232, 244)
ORANGE = (224, 110, 30)
YELLOW = (245, 196, 66)
SMOKE = (150, 150, 148)
KEY = (255, 0, 255)  # sentinel colour for keyed blits (never drawn)


# --- canvas --------------------------------------------------------------
class Canvas:
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def _row(self, y):
        return y * self.w * 3

    def set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            o = self._row(y) + x * 3
            self.px[o:o + 3] = bytes(c)

    def blend(self, x, y, c, a):
        """Blend colour c over pixel (x, y) with alpha a (0..255)."""
        if a <= 0 or not (0 <= x < self.w and 0 <= y < self.h):
            return
        o = self._row(y) + x * 3
        if a >= 255:
            self.px[o:o + 3] = bytes(c)
            return
        inv = 255 - a
        self.px[o] = (c[0] * a + self.px[o] * inv) // 255
        self.px[o + 1] = (c[1] * a + self.px[o + 1] * inv) // 255
        self.px[o + 2] = (c[2] * a + self.px[o + 2] * inv) // 255

    def rect(self, x, y, w, h, c):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            o = self._row(yy) + x0 * 3
            self.px[o:o + len(row)] = row

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def circle(self, cx, cy, r, c):
        """Filled circle, scanline by scanline."""
        if r <= 0:
            return
        for dy in range(-r, r + 1):
            dx = int(math.sqrt(r * r - dy * dy))
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, c)

    def ring(self, cx, cy, r, t, c):
        """Circle outline of thickness t."""
        if r <= 0 or t <= 0:
            return
        r_in = max(0, r - t)
        for dy in range(-r, r + 1):
            dx_o = int(math.sqrt(r * r - dy * dy))
            if abs(dy) <= r_in:
                dx_i = int(math.sqrt(r_in * r_in - dy * dy))
                self.rect(cx - dx_o, cy + dy, dx_o - dx_i, 1, c)
                self.rect(cx + dx_i + 1, cy + dy, dx_o - dx_i, 1, c)
            else:
                self.rect(cx - dx_o, cy + dy, 2 * dx_o + 1, 1, c)

    def round_rect(self, x, y, w, h, r, c):
        self.rect(x + r, y, w - 2 * r, h, c)
        self.rect(x, y + r, w, h - 2 * r, c)
        for cx, cy in ((x + r, y + r), (x + w - r - 1, y + r),
                       (x + r, y + h - r - 1), (x + w - r - 1, y + h - r - 1)):
            self.circle(cx, cy, r, c)

    def line(self, x0, y0, x1, y1, c, width=1):
        """Bresenham line; width > 1 stamps filled circles along it."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        r = max(0, width // 2)
        while True:
            if width <= 1:
                self.set(x0, y0, c)
            else:
                self.circle(x0, y0, r, c)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def poly(self, pts, c):
        """Filled polygon (scanline)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(self.h - 1, max(ys)) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if (y0 <= y < y1) or (y1 <= y < y0):
                    t = (y - y0) / (y1 - y0)
                    xs.append(x0 + t * (x1 - x0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(math.ceil(xs[i])), y,
                          int(math.floor(xs[i + 1])) - int(math.ceil(xs[i])) + 1, 1, c)

    def polyline(self, pts, c, width=1):
        for a, b in zip(pts, pts[1:]):
            self.line(a[0], a[1], b[0], b[1], c, width)

    def ellipse_outline(self, cx, cy, rx, ry, c, width=1, a0=0.0, a1=6.2832):
        n = max(24, int(2 * math.pi * max(rx, ry) / 3))
        pts = []
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            pts.append((int(cx + rx * math.cos(a)), int(cy + ry * math.sin(a))))
        self.polyline(pts, c, width)

    def vgrad(self, x, y, w, h, c1, c2):
        for i in range(h):
            t = i / max(1, h - 1)
            c = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
            self.rect(x, y + i, w, 1, c)

    def blit_keyed(self, src, dx, dy, key=KEY):
        """Copy src canvas, skipping pixels equal to key."""
        for sy in range(src.h):
            ty = dy + sy
            if not (0 <= ty < self.h):
                continue
            for sx in range(src.w):
                tx = dx + sx
                if not (0 <= tx < self.w):
                    continue
                o = src._row(sy) + sx * 3
                r, g, b = src.px[o], src.px[o + 1], src.px[o + 2]
                if (r, g, b) != key:
                    oo = self._row(ty) + tx * 3
                    self.px[oo:oo + 3] = bytes((r, g, b))


# --- PNG -----------------------------------------------------------------
def _chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data +
            struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png(cv, path):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)  # filter: None, deterministic
        raw += cv.px[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 9)
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0))
           + _chunk(b"IDAT", comp)
           + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


# --- bitmap font ---------------------------------------------------------
# Glyphs are 1-bit bitmaps at a 64 px master, packed MSB-first and
# zlib+base85 encoded. Each glyph: (advance, width, height, xoff, yoff)
# where xoff/yoff are the bitmap's top-left corner relative to the pen
# position and the baseline, in master pixels. Generated by
# tools/make_font.py from DejaVu Sans (free licence).

FONT_REG = {
    'chars': ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~–—°•·‘’“”…×',
    'ascent': 60, 'descent': 16, 'master': 64,
    'glyphs': [
        (20, 0, 0, 0, 0),
        (26, 7, 47, 9, -47),
        (29, 18, 17, 6, -47),
        (54, 45, 46, 4, -46),
        (41, 31, 57, 5, -48),
        (61, 55, 49, 3, -48),
        (50, 44, 49, 4, -48),
        (18, 6, 17, 6, -47),
        (25, 15, 57, 5, -49),
        (25, 15, 57, 5, -49),
        (32, 30, 30, 1, -48),
        (54, 41, 39, 6, -39),
        (20, 11, 15, 4, -8),
        (23, 17, 5, 3, -20),
        (20, 8, 8, 6, -8),
        (22, 22, 53, 0, -47),
        (41, 33, 49, 4, -48),
        (41, 28, 47, 7, -47),
        (41, 31, 48, 4, -48),
        (41, 32, 49, 4, -48),
        (41, 35, 47, 3, -47),
        (41, 32, 48, 4, -47),
        (41, 33, 49, 4, -48),
        (41, 31, 47, 5, -47),
        (41, 33, 49, 4, -48),
        (41, 33, 49, 4, -48),
        (22, 8, 33, 7, -33),
        (22, 11, 40, 4, -33),
        (54, 41, 34, 6, -37),
        (54, 41, 18, 6, -29),
        (54, 41, 34, 6, -37),
        (34, 26, 48, 4, -48),
        (64, 56, 56, 4, -45),
        (44, 44, 47, 0, -47),
        (44, 34, 47, 6, -47),
        (45, 39, 49, 3, -48),
        (49, 40, 47, 6, -47),
        (40, 31, 47, 6, -47),
        (37, 28, 47, 6, -47),
        (50, 42, 49, 3, -48),
        (48, 36, 47, 6, -47),
        (19, 7, 47, 6, -47),
        (19, 13, 60, 0, -47),
        (42, 38, 47, 6, -47),
        (36, 30, 47, 6, -47),
        (55, 43, 47, 6, -47),
        (48, 36, 47, 6, -47),
        (50, 44, 49, 3, -48),
        (39, 31, 47, 6, -47),
        (50, 44, 56, 3, -48),
        (44, 37, 47, 6, -47),
        (41, 34, 49, 4, -48),
        (39, 40, 47, 0, -47),
        (47, 37, 48, 5, -47),
        (44, 44, 47, 0, -47),
        (63, 60, 47, 2, -47),
        (44, 41, 47, 1, -47),
        (39, 40, 47, 0, -47),
        (44, 39, 47, 2, -47),
        (25, 14, 57, 5, -49),
        (22, 22, 53, 0, -47),
        (25, 14, 57, 6, -49),
        (54, 41, 17, 6, -47),
        (32, 33, 5, 0, 10),
        (32, 16, 12, 5, -51),
        (39, 31, 37, 3, -36),
        (41, 33, 50, 5, -49),
        (35, 29, 37, 3, -36),
        (41, 32, 50, 3, -49),
        (39, 33, 37, 3, -36),
        (23, 23, 49, 1, -49),
        (41, 32, 49, 3, -36),
        (41, 31, 49, 5, -49),
        (18, 6, 49, 6, -49),
        (18, 12, 62, 0, -49),
        (37, 32, 49, 5, -49),
        (18, 6, 49, 6, -49),
        (62, 52, 36, 5, -36),
        (41, 31, 36, 5, -36),
        (39, 33, 37, 3, -36),
        (41, 33, 49, 5, -36),
        (41, 32, 49, 3, -36),
        (26, 22, 36, 5, -36),
        (33, 28, 37, 3, -36),
        (25, 23, 45, 1, -45),
        (41, 30, 36, 5, -35),
        (38, 35, 35, 1, -35),
        (52, 48, 35, 2, -35),
        (38, 35, 35, 1, -35),
        (38, 35, 48, 1, -35),
        (34, 29, 35, 2, -35),
        (41, 25, 59, 8, -49),
        (22, 6, 64, 8, -49),
        (41, 25, 59, 8, -49),
        (54, 41, 11, 6, -26),
        (32, 26, 5, 3, -20),
        (64, 58, 5, 3, -20),
        (32, 20, 20, 6, -48),
        (38, 20, 19, 9, -33),
        (20, 8, 8, 6, -26),
        (20, 10, 15, 5, -47),
        (20, 10, 15, 5, -47),
        (33, 23, 15, 5, -47),
        (33, 23, 15, 5, -47),
        (64, 50, 8, 7, -8),
        (54, 37, 36, 8, -38),
    ],
    'data': (
        'c-q}t&2An!c4bWsy0Qqmvg}2}%wzPz_!wYbB#+Qb527iSpoNxtgK?fDF2Mn`i{BtB!9cup2?`(zqKi4_T-K-GcH7;ZOe3;czbx{S'
        'y!YH6-f#GHd;RhJ&G5`==kyosE_dh6_4Jp;AAIg&a_!uY&Uts>T(h*ZbN$GM4w}W)cRPEBy7%98lf6szUE$v`4>|C7p$9z=3C;7n'
        '#OAxnyZT)_vrTn<|J{MTL-T5)Qxj_Ql!sMqF24cE^<9gr4ljCKzd(73@(KlC^u>XQ86+$o=SUJ>`s4Jf?I%!hIJ*H~=Wc9L@7m=B'
        '%1hTRuUx+@uKzTn0hWxiy0)k_=OW5wam|cp(~7?FzDe!{Xncv`yy_>n_<wEY@FQNQ?&zlU;R<6uLqQ{{DP?j#f0puQw%04i>bk<2'
        'aiMU`qG9Kn6gk)399V->ff}4R)HuLDOijYS1H9!wyyZVkqNcGQHF@5aVdr+7V0^~qNX^2D#*(52W@h4Iq^RX7nKjy?8cmr3S$4&j'
        'Ae5_8xFECVsUJB}&Nqpb4oIkD%RANxZeR@(3KB>t*BD)pBhUqT3rkEg(UaFd4Qj{H@-tM*n034*?|Bi*(I(ADgGIyRrf_OVD8DC>'
        'U3MCV<2sV}3a7a6GR&Z<OAeRO{Q;LV2RHD5rtz2WF7?zZL>}5jvO97XRL#%oM->u30|~DAw35IR@ZRwf$7UJY?0i4_xm~g=F7#8E'
        '+Kc4EH2ASuJ6!h5fgfEwIZdw3375Vcq6cvF<hqqKg}KK_R}$i9(2qq3b3;BG!D$e;gm)0c1<W^vu`dfq^dQRr<@$X8pPazS??;c('
        'r4|zA$AD-1%R!fOZ#SI%XKw9*cYJifhiDV6;>E<J)JkHx`MlYl;|<%`u@$~jJJaX;!EL?Ko8A7B#5bZ?NYPihT1=ko_8Yf+^L;!0'
        'ko)#BzYK@zGBvm7BiW+GI$=>T?VMvQ+v0}nxqE*$$G(5RyzI~1^6hu+^xg9<6Qv{q5(ln67he!53>6!aCBLqsK=hV}Pr^_kYvf`4'
        'g)RO}#co;s+Z6kY6uQ&2>!xMb9hUvy^#}W#*&eZoO-e%B<<TR_As!9SK3e!Fkb>tQ`B4Z)soVX;qi(+6vlg$zBKFW*6mIbU*eA%y'
        '(&1l|yTwIR4M%tlnd%^T4Ftqxh;&4^;Wg0l9i|+EYp;PMx0szzXmmiOKpA_33g@Ws@o@#T5YU3JE%a!iy8_MX0wc@7hYYe;(f}EZ'
        '5cvpM1%V*4<zi|<i;V(u63XbMFmzhO_<frMGk=>?Z>;z6?&Km?6o3Md0gonB$Ub4ZfupZbFiV$YCh#4&&C^`K5`_w&RDsD}^A*u^'
        'HT>Kj#gV{9P!^!p8vLk#<`y5+siXAXyQTQNLwSt?OJs%Q0B*rIIN_RQiZl?$FjM*evwCE^&1cF+d+l4x2Xd%e%v9h2W+P_bUaop%'
        'E9<>dpEb3#X~cIBiv`m>gLD=^I^Z3=O`x(tvh9YNMxF6PP(tu>o(c_|*xaDX4%6Nr&tgYMo#KxmYSekuoPoM@qV9w|5r>J%K<)*X'
        '0|X43X$EM6B_VZ$UzhRDj|1B4H(Yu{XxQ*+vH@|yr5%T=JUMk@0jbZsD&V2=r2NbhJSev-75Rk1wlc~}i=+`7kd-uBWGj-vRb%OX'
        'qHOQ``c3$Ev~i5K03$SNSCrgYUyuQ=A9ZS!5HF5qv$za1R9wgP9oISwu}%Q_mt$ua)@_*D1(YYOamIQNw4B#2!&odR;T@Lc1JLsZ'
        'Bh47p5Q#Wg$=5&|z)=S{Y5_+L;b=uy0|5=xd#t;E3xK>p3v&cZ`Ke#}<Y^NuA~+P<nY4Yz&V;+1*CmY<^gDL1q8gu<;9+B48<QTp'
        'y<oTZpdi-A_r%CQZTGqE=4ZPDk~&Ht7lgw?$t~Cj2og@A2xzYx4C6EOv`tKpiJ_%M!DwkdCO=V6G`U$@0z{TFX$wuOLWMH-z_@;C'
        'R?r+dwP$GI3Uhz+oUW+KM5^G1T||HqR(kDox3-*HmVnX`JL0?_2{Gl4oex)<h~ugiY?t_GB=2U^S)fDmzOpT<B+%fYuROIiUUs0N'
        '1NXF0CvE95O~>G6_-5B|kgnh;U8c5xPr{Tdzdq*GO?<lfAFxE<f}6V8IH@siqN_3qlh*p@9{+7G%*x2&czIgK{@SfV_D6H}?flBO'
        'vca3NdVeCu1%gZw77Fsolj7$>2Y?LBm%S`~0c5FF1(j4}Ht#0Os%NjgO!vD>^B%(e%dxiZBJaC(?-$U$bB=-}i4r>AH{{%x{@q!8'
        'l*n?|;(xns7R>RGT9C^jvN|KnE;UYqp<NcaX?D3Ev&{yf%zP!yMlAbjO?6sr4)3OQsZ*l%L*ClZ(r6a`V5>=s3>t&*37&&nSzb8*'
        'UlQO!EC%Ur_BZ$(AOI<(8Bm1c;Pv`6X~_Gph%H&%3I@HqdCE_MouI}a+&DSf8ZPIcvGwU>Wn<9hBxX$z4a_7C2W_n>@=nuh4f#=i'
        'B3%>N+oD4bHBSfB+0Al*$$il*3H`lriTdKNE>V8|)7=1Ez(#*wT9|$A&+rc&PtwhiahIL@m(QGT@1L40J6-DY_Ck$y7izjcRY&oV'
        'qI+H(iFmy_lH?gY@GI;tlIyF_yPr}G%y4*HW&>>ZPnwWsHq*@}%P(X~`r(>L0*TEo10rs7#y8QC!j|1+hK;dO!_SPh%=j53Y#;dH'
        'AnW2x76l0;rqk8t!X3)?GQ(3Uh)Y8g$I)HoC1Vj&Cyt^04kb($q+%U$29FS9<+sS~7_{2r2gz_>4E7*T92~7Ae1Xs5lJZikpG}#O'
        '&efE?1WUUAQYgZylm>y?uvP)YX7MewS~17vZIU@iSHOi6h{5}0?#n=GA3tCXUq9&?gUh{iqEt?qYoif0I(`z_2Gj^m2uIAO`l6d7'
        '7iXvsXlTgDSnDSdpTzg1vPSy0UbucCNrDIt(q(1h#7!RhYy{*+^2m-B?DsVAzf%Nd-M~!jWb!m^h`N6%l`k7oq9%R}``8R?$kLSU'
        'Y1Q@(sh8-UG<nyqHIBnKqK$_HIHc`I`P;@}>?;cpBUKoQW7J`8iUs>%hGsAZ4vj)L@sz-HK@X3Io~thwpmlKXAS>?C!F|o)xdtBf'
        'p?*byXc1MUPn7y%)NkXMx3Mi6;BD1sdsA_|v+43f_sHKf;vT<#<d@;{<}1Gb%<E^Y*oV$5PqV)1zx;%`z;`Eir?30`=T8;gBsA<z'
        'GbEcFCYA)pDRKa<LZ9YGIyHaKZySk=Spn-l9BF#(?oHgIwuC}5Vj^Rz3J_9m$kX&6VtLJY#0Nc;ImplHZUA?MuzDz%Jt3%(e-xQ^'
        'gO=t<C`&g!5zYq@KLQjKl{eH(HcWXT9J~B^Sr@<Q#q)pvJAHj=?@#~c2vs$$-4YIS|Eq7Np<O)BtG_CKDc$@7xgfw_X;vCi@FHA1'
        'qzMBS@iQJVB-N#c_CH*p6|4f?4SpNp5;0r`cJrr1eynGcv9jG2(c^sHti)vTH-)iWTsOn<nwsz(%>V#BJQp}ci>x_vL_>$R6~02*'
        '!Zk&Yey&7-VJck>kyNC@AgR<FZk@4VvSo>nB1pfl+loig?0=%?xv_^cT$LNhd%91YH>yqCf5K#6mp720as@Z;HH5RdDrc}oA`Hj='
        'q`*?SEEfx8G4EV|T#jMo6<C-De(k6Js7whSBdoZCzQ6!FEc32iLhh!6u8i4_Fv*W*zc%TB7~{v7+V^u`+;Gr9QqM=4y^z?EkqDTI'
        '^a{dES<Un{B6r$)sE2to&^p;_=1Q!4gRSm_$d;R{hhjc&VT^k<GqAHwHijecKFaNe{~9y+qtMpK11_-Q5vCqISM-k&fagF9_#YRr'
        'kuy~_46m5mgbR!)gMrJ`PjJ!Td`v(k)W-$p1$=f~Cg2uy-Wf>Axad9<&Mx@v8W*8tQ}f=!dy}>WE8W>#A31{%md*ye%EL-pLW|(j'
        '5(e~9o;Y!Eg(Ce9Z8d0bDk;cG8==j@)VB&5^0Ft~x|PUkmqKDQe(B{yz`pF#KHIlY+f^6u_r3X3(O@xGQD#JnUL#$jumRcFG)x<@'
        '4Zc$VL&1yI;$__X1?+T;Jgkg@tgeMoLTi$tD_WL}tkcS5^aK`XbMLjsYsh$0!r13%=H_YLQzfhX3RB_H>l#e(<lnB!;;IpXl9gUe'
        '894>8t{3_`krUIUPEluya#m{>@(UGk)Fq8&g@Nj2t4nSfV2m=B-+bAneYS7G+LaR#?|NHB!z^-)G7)L?igX)=4JcGYcC90}!JC(F'
        '4z6u!nrqg{Y6yxttmdmlg~*sJP}RB={K&P!H1`Xr2_qrAr4|91Vk}|#Ojm{GaY7{sC}`g*#gRcfR0@+?Dz>AkuswH7vUSIO2vlNt'
        'tW|e&?at+`CC~1-^8(x(jll;603yA`WK$>4Ng~1NmB9>y2$<AbOi=`Ia8rcXV*D?u%(|u8QEN52IP>lO2dc4dA$ozmz%JQj7rPi0'
        'gq6-z2%k=~raro7+I;fB{|C8iHnCa*oJX1+N2E5G@y>B@)@lgq(IMS)eg1zOxF`(2Dm=izsP^Vu&J{T+dWx0)tttr&!s|)<g9i5u'
        'xb(D`8MlVm06R@M_r6zaQMb`HQeIEhm1FjRHg3r<7GV&~S=>P(h#HNcHQs1L4=j&oij!GPje!IC05h3xtpSffq_i-IA|f?7GPPUC'
        '1X_2gfs~G-hmZG>mS8CBw@^&gXAICl(MkpFBRC8;)F5iz-^%;IPmKZXBSS<Yi`ywYQEcnhTNIx46cxwqWmXFewFKMnZ9k3@{#{ZS'
        'ru{f6CbK(0YZ(67BwRW;5Eyl5FhnuZgPkHdu#*(lNjt@O`Xk2CaO*jpqi4E9lbeMZ5HOva1r24Uy}(AAb}pftl}Q!@y0Y7Wxh{a='
        '8O9n&j7)r?C2Y5$o7#)4y@?&8P$whvLs}Spy!9tz0~R7vc}A|zVHLtsgtf@q{#*$#%3~m|Q6JALyzJ^NAc=uq7RJC)x@@?^_>9wb'
        '2vrEJb}~>VldN2IItOGITI)?RhT(=2Ltj1F48RLs%hXAObSs&aS{|!AZ$@C0s$I5aHQCKu_Do~J_qlo&E^D(iY>IUt-$i~CNme9B'
        'h^@m&r7<${G8v(I+;iu$qcSobEkOy#OGW)w8lOVhU!<x?;Y@K%+)1HAQ5P#kfvrl{P{ru5C@Rgyb<n_NT5%uFOs}Ag!n_^&w0Y<M'
        '=Lf2?!mynZ(-_Jq#n(Lv&A*l-Y=JkaFX?^R0dWh|J*ryvvAYLV^|hAvVbyjY=KIA}J98?wO_4X-M#=inv4-eo0@81H+BdD>uyRtm'
        'nh*mau{;((?(<gqnjzC{xh_vW;ud60kr|$T^wVuG`|O+A_L~(N{bPBvGB=JHcfZ}~uIU;;oi-7UdD~rzZ-^rls;GFU#D>xrD^@V|'
        'g+{Y8Yma-GRTqT#OibhxRTR?@0{2x$AmZH4n1jULx$_hiDYp!ixlb?9%|D7&_M7=N^Tcvjz3ez9tH5eirt4d%TE@ybrGqp!A(bke'
        'irYh7Q@0elEpk4lk|KQa2xmN&<0-EF2&N3~;eLL**@gEvQlC};RAj)y09!l20Q7GdKySJI6OTaG1$UMTV=XnPFWjFVZuaJ9@{jIU'
        'uoNe?Few5Pfjr@uU6iRD!v32w3TT*uqE_-=X^=AV$UX3mv8g#g+J1oO{mIgTw9{dU9s*JuukEjBbR6x|m)oV~@G$tpW_<!TDBQf*'
        'KKpF&$acQ2z{x-pM~g4-mr$;-PPa=rEX<>UF%T}HErIdc48LCF7_+ob%Jj@LEBcP#vmLg_cG<rAVShn;>F+_u+r>=($+A+-ahb`m'
        '?b<5CfTk65(Jrz@RGEuLKJ;&>#JLAkgGIM><5<}CEJtnZ7HgE3QMx1aI+e+D!-vT_sj-BQSt^$H<?868Ln7pu31SRa41tJMo+0`*'
        'GC+UBX6j=u^fR@8;bTF2Oabmuzyt;G!J9t$;^9nsdHxVWr^1-VR>J*qP|NVN#G2z5)dt#Pn{1nXurKz>zDWaU2{j{fs6|Oyf21))'
        'Z-4eg9P%n%-AVc3FfeOon=-_fhwyVR@$KPjpyM$l&zE_KW&T7^n!{Tx%o*6~WRWRLk92qnPLy;?JSG3vzy4GenzMb{pNN^mj<5g6'
        'yM6V$hhP1F3GGtihc%up2VXDk`$B<cmQy&g9M6@eIFKMgW5X<`zXAkbm^`z}EoiTkOukm4FxB&7&#&<Qk{(c@g2H!9&SIu^$BgD='
        'ZL^P>PilSl?+GYh6zMmEnb03of5x9E%vt_=e_nDdOIgCZIiA4YhQ9$EUKKwFjL^S_-T96o4sL?e^!zw&H;di4-_OnLemDG`Efb+w'
        'q}kkRfZtR`kT}ymiRPfL`?RWOG;Mr<&68=52dbF%4O?Is3WgBFO`cLdhb7Ft!T&58e9e?%=xSl^0O*k_=B|GRFfmJmx*9s-ZC03X'
        'pRYXpgtq@lbAZ_a@`sZQ3b;oB{;0a3#Q`<bUNP&E`G+(~+Vu5Cjb+`IQ)rV*!0Js3FyLe{0Ug1^P;fm{(6~ysNr6q4=1G~Kd1gi5'
        '-B>zZ$M)1N+h;%QkNx(R$%ZBVsx(q7{@vRWe9q<Sy1Xk*P_UHF9>py0<08NOl6tpM-X9IoiHXw-<B;Fu?VlFu9cJk7Y{r>_Z7JbS'
        'vBD(vt(1x^_jt>-3AKJb!3@3zGsiJ}C<GP$#B1RmM!$YuHOtPpmDK^RIQ{kdT|t9}X}xPp`#Wj#gt5?|pR)*ne~a5si!3(}*@T?7'
        'pUlvU?;vtvj#;)~d3P!cW6sSgrd4tajOz9>SxP07quXV$WF0?p>3|0O#Swpoa+erADshPJiD$wz13Jtyf^h&e(-dUOL-JedHHB8;'
        'KnkhFf-SGi0v?JGCrMGO2*xcpKpED74!X1>9Uq2)%GB9$)`t3=mGPCEtGTbogXR*Z+Q8#Dv=@u7$I#AD-T@zahL~vW*ztHe2n;JR'
        '+J)l)zevY-BMj31-0gBb@>fPWdhUtb9hu-~N9FD9j}2p5j0`Yt!#%DZQ>2JeRA`186;nrNhdD(IM`|r%{p}PZGkrF%L}sGm0hV}U'
        '`;7_^DTnE7F`sf(3~11H09I~QcAmHBp69~kn(-viBv5wm7lYPt%pfRj@tPd3AKGQnI4E(fNs4`v18QP?u!!fNAG!?oDMOwL?lL;t'
        'vUTFJ0>H{pU2Axg8&29dWL!gmj|a)~+s!^_eoLTNNVn8*X{>Y9*xqCLV0kq+_Vb5|5b?q39$q~8!H2I7-l&L<qJVpMudgS|S?MhB'
        '@~NiWL~SMrWIS`?Mywz=dbliV($Y4ArFc#?dGqdtewoN<$Nn8noJ8o0iBsiQ<yQFlUJ|Iark})qNgqn|6G_~n<Q}pGNN+#>+gJTB'
        'n)bkrC^4$vC!+pb?~h*G(PTy`MvArcHifg&UZ)zG|FT)!zaSgV8s<W#Be_#G+8I3i4hsaegE`o7SFL6lPt42W!hXvgsc*JDKi8ID'
        '@CRw2v&2BjTR_oYnWxI+j#h`&{blZ6yOaYQ(6~Y#l;`T9z4=ACWMJ}!X<`o!s?2l+_*~76{iPS((VPxEx=BMgd7oB5P4s7%dGIH1'
        'm$dWU>HMmh`*wQKj|bkt;h0nZb^$yC_H$^{3KOe;p8z7^M9DPA3(U9yco7cM00@VPkJ^EsGhbp(XcF!1Xd4KG7{!-*<-}(Fs^a+<'
        '3ncoFm|yoJA?)33@TD!BsCY87GcA-&?9xUklm9JZ&18Vq(%fqdPIjc$iCRQC7~D)$KwF3^Xcfi^ceQP!sJ1pnwH2z(&)57>;E!nj'
        '5Ep;<KZX8qH~'
    ),
}

FONT_BOLD = {
    'chars': ' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~–—°•·‘’“”…×',
    'ascent': 60, 'descent': 16, 'master': 64,
    'glyphs': [
        (22, 0, 0, 0, 0),
        (29, 13, 47, 8, -47),
        (33, 22, 17, 6, -47),
        (54, 46, 46, 4, -46),
        (45, 36, 58, 5, -49),
        (64, 61, 49, 2, -48),
        (56, 51, 49, 3, -48),
        (20, 8, 17, 6, -47),
        (29, 20, 57, 5, -49),
        (29, 19, 57, 5, -49),
        (33, 32, 30, 1, -48),
        (54, 41, 41, 6, -41),
        (24, 15, 21, 3, -12),
        (27, 21, 9, 3, -23),
        (24, 12, 12, 6, -12),
        (23, 24, 53, 0, -47),
        (45, 39, 49, 3, -48),
        (45, 34, 47, 7, -47),
        (45, 34, 48, 5, -48),
        (45, 36, 49, 4, -48),
        (45, 40, 47, 2, -47),
        (45, 37, 48, 4, -47),
        (45, 39, 49, 3, -48),
        (45, 36, 47, 4, -47),
        (45, 38, 49, 3, -48),
        (45, 38, 49, 3, -48),
        (26, 12, 35, 7, -35),
        (26, 15, 44, 4, -35),
        (54, 41, 36, 6, -38),
        (54, 41, 21, 6, -31),
        (54, 41, 36, 6, -38),
        (37, 29, 47, 4, -47),
        (64, 56, 56, 4, -45),
        (50, 50, 47, 0, -47),
        (49, 40, 47, 5, -47),
        (47, 40, 49, 3, -48),
        (53, 45, 47, 5, -47),
        (44, 35, 47, 5, -47),
        (44, 34, 47, 5, -47),
        (53, 45, 49, 3, -48),
        (54, 43, 47, 5, -47),
        (24, 13, 47, 5, -47),
        (24, 18, 60, 0, -47),
        (50, 47, 47, 5, -47),
        (41, 35, 47, 5, -47),
        (64, 53, 47, 5, -47),
        (54, 43, 47, 5, -47),
        (54, 49, 49, 3, -48),
        (47, 40, 47, 5, -47),
        (54, 49, 57, 3, -48),
        (49, 43, 47, 5, -47),
        (46, 38, 49, 4, -48),
        (44, 44, 47, 0, -47),
        (52, 42, 48, 5, -47),
        (50, 50, 47, 0, -47),
        (71, 68, 47, 1, -47),
        (49, 47, 47, 1, -47),
        (46, 47, 47, 0, -47),
        (46, 42, 47, 2, -47),
        (29, 20, 57, 5, -49),
        (23, 24, 53, 0, -47),
        (29, 20, 57, 4, -49),
        (54, 42, 17, 6, -47),
        (32, 32, 6, 0, 9),
        (32, 18, 12, 3, -51),
        (43, 37, 37, 2, -36),
        (46, 38, 50, 5, -49),
        (38, 32, 37, 2, -36),
        (46, 39, 50, 2, -49),
        (43, 39, 37, 2, -36),
        (28, 28, 49, 1, -49),
        (46, 39, 50, 2, -36),
        (46, 36, 49, 5, -49),
        (22, 12, 49, 5, -49),
        (22, 17, 63, 0, -49),
        (43, 39, 49, 5, -49),
        (22, 12, 49, 5, -49),
        (67, 57, 36, 5, -36),
        (46, 36, 36, 5, -36),
        (44, 40, 37, 2, -36),
        (46, 38, 49, 5, -36),
        (46, 39, 49, 2, -36),
        (32, 27, 36, 5, -36),
        (38, 33, 37, 3, -36),
        (31, 30, 45, 0, -45),
        (46, 36, 36, 5, -35),
        (42, 40, 35, 1, -35),
        (59, 55, 35, 2, -35),
        (41, 40, 35, 1, -35),
        (42, 41, 49, 0, -35),
        (37, 33, 35, 2, -35),
        (46, 30, 59, 8, -49),
        (23, 8, 64, 8, -49),
        (46, 30, 59, 8, -49),
        (54, 41, 13, 6, -27),
        (32, 26, 8, 3, -22),
        (64, 58, 8, 3, -22),
        (32, 22, 21, 5, -48),
        (41, 23, 22, 9, -35),
        (24, 12, 12, 6, -28),
        (24, 15, 20, 6, -47),
        (24, 14, 20, 4, -47),
        (42, 31, 20, 6, -47),
        (42, 31, 20, 5, -47),
        (64, 54, 12, 5, -12),
        (54, 38, 38, 8, -39),
    ],
    'data': (
        'c-qxmO>XTva+aPN(Hk_tEZ`w}KnB@F<1tIhFoTPx91lEncHk_bcW`8Q;EduWScV54T8;x)hGnw9?<-R09RJ;)zV{{Z_2to#s3KV`'
        'R((}0I^3s|CEX<dm@Z;?=gWEYcgfA+EOt{mTq^yvuc}>+Asjr%_F?Y6<g%)K@B6BXH7GW7J5`k%yP>K=_2;Upmu5yIlN;ZuS110o'
        'ES8St6j+|Vx{cQZ>G5@=*A1i>sz`cl#@baqHKP}2(Yq48BNp-1?S8-8VZYnfOtfaU^<H(Sa;R3#?_RjngWG9r*dkh=9WD;o6_4UD'
        'T^!ARn%kr3`k%u%S1m3oT_j%2yZ{NGmI@>yF498ojV=?^x1r@Twu1&!RXu`p?g$qkUb#bE{0}ew1s4w^9-#?LJl-Nl&I@Zqxgp={'
        'G=Dg*y^ALQ=R06q$M+YINCWuD38^YDEFI6_V&$f8BwItDz(bov%G1z|4c?1YA`LgSn%&Uj!B90zEfMNQH#y8h!h<XUnyt|foc~lu'
        '&Q%lr$mv7Nq)~-5@hdt+8epX6l3k8$T9cdj85^*XQ|mSS(2%33*WK~4KS+(lSVO?jAT>Qkik>c{!68rvIRt#=5F}X`0!VTQWDkc>'
        'Y0P-p_YGbrw>SiHE1WHqyIOO}>BLJ|QXXG9w6Ij_GXFcRW|tPNX!SJd3q?btpY(u30tYC*3#Y3E<9TbWenl-2Y4`%D&PGv6f^U-w'
        '%bL{jezfPKUWw=d`&m;EA(|6f9NQ>4O?`Suqo4c|VjEj5>H+`8u;A9*LMx#Y;hDG4!3muJ1$2VK9wrQ6a*-oryAU7r+ohp_JYik}'
        'CXF>UNw$=o7Wb<!$0B%zFJNDXA+qCAFS|c;jRw%~Dh%Lg>O0)%{nVg?x;ygjz@ZL$)XnIqSHVi}6}gJNQKunODMVFE&(I`q54i2Y'
        'OFUQ2(iE!UiFH6U*(2UiKf<(LSG-0;<S$0rE%sQitxs6_#mBUMu;$1Y&_q>zs$TwY@c*#?)SQo>-1+>eyNRE|HCb+&iIW7;#w_ta'
        'uX!(VVnaGY-5b7xch5lM47B<;+Q0-+2)UxD3@C?^Ov)!kxay>Jr?0F?{hOX;2{h?41REBYEN;!({E((GFOb1A*dZ6Y#n0g`U4tDC'
        'OCb#DAhy&eg9oD?*rjLnCZs2J4V}GDo2UKXnVP_U-I#y7A^-Zm{7OmKZ_K~c%KC-=$-mPV5nCz!`6FUR1|y%TF=A!L$Wt51;Fi_d'
        ')Am7?buc(%$93ODD4lMB9`N80^bjTke8S?tPe2Pd2@`lp3%8+=K}~g$;`NLg;fZSDA@w!*_Cd8rR?F1Tl?y1r)J4>=MzI1XF4i$%'
        '`Sk1?`%LjQT{4<hl{S@P4OE#NDb-<6C7EZAkT&$ijRn2ISgC({Q>Rq6zsrpx>J;*)vI1V+=pBu+4Yn@;g|o#KzOV)r{4F%p(+EQV'
        'bCmuAO=O!yGr?8=suOl|GH}3}v>~i*$cVaP+*Y9Z3N(}Hy-Hv7GjzgCVtv#Uav%eT%8QY803^~x74@@GmeqT8q49W$@}NoeAlU3c'
        'vPtd8@Os(cBu-4$cMXbc5KmrTxbzp)dBRFdo54Xm$>zdyLx_on&IHkTlS>tp#(FJ;UfQ(~cIei^-*SR4SR7M`kBKrc>2*ZWuxJ++'
        'Gfgjxj<%(vvGFWm9#K$CC@U}$j!>r*tA720f@q1o|7;OtJO~i7P%gCIqt8&)W>uB=LPy<0&bCy{ek512HmbtyZ0M*f>zR~>JxXwE'
        'z;I}Z<?khMHiMMe+P-CkM3I(!XDRu2R^oa%hav#<?99V(#jjaM!10U{9D7}Oq~q5N-*fj+ZK~Hkb{KFE5o{?;Kh=g|`phKHp@u2b'
        's^LPRdnZ5(_GV_*7>d-ZXJ=_~0R311$E?|Lop`FkKvkHs{!Mp;cGr~qa{?*&6E2yW#>~te=6v$NabhA>y0qPF%fOc<f)TO9(Qp_0'
        '@$i|8!WT)kfmXw(>&n?%obT1E-l*4nP%pk!ul=B&xe|k!1IL2%#>pPLtZg*)a6J#;UIA8JaYm2GZP^?G-7B(}x48bo?1?hLTN$5O'
        'uAQXTe5phumu+Zek_AMq*`S)gqj8g6g9+^xnx%W0#cUCAYvQd@6WS&AYgr|OPU+GVsj~sOl-0U?je1ojoNLE^(W8}k+e(CXJ>ckF'
        'DkjxL2-0&xErDLj7}H$KQg`fXSSarI6vYd=5*@Uj`ZcXVfwruDH1y1h=NRU!DKNjMtcNgXX>jQ$esdT)mQOH-va5s3k~$SoGMhr@'
        '^tLHH?Eg;Hi=USj9tx~`f%0CxXn~ivDo+^XA#h*^CoR-bK5JF|k;Ok$+1ab5*ra)6lFS&+W`bN64;pX@3r8Xhp7_#|Es_``hMD#7'
        'rhg>xMs)wuoXU_d87473D0MTh9;i8mauZ)5YOUv|7tp)<f}eLW`VK`^oC<&7CRJIjI#ZGBSoQ|6yu9oU^%$FEP)*aDOi2-#S*L4b'
        'JnfA=nf>Dq`<)S;@~Y9K8Grtj#jjQNvV$xRt-~3H(iy<w*fv9Wo@!ZxUMhxuf6_ao=oeWgA2p#q?S4RM)RKiP$>`;*Dc8byA%@lN'
        '!!T*IJI&>XRe3jMmtQ<`Hi<rE<|To%xlTsLGm0hIpyh31w#()e1%(51xK1IImi`77<h-~M8e>`7D}bGd59+_Ax#Ox`ntS-Coj&GP'
        'A5+5*$GFPF=*IfRNAtl)n?J7gy1N#!?o6cpnHoxmQWmL}5@zfP(z{gbU}D(F&s1aRe9Ypf$X8VyKm#MSfsdv)h786Y;o-()Dw%wh'
        'cullO&TK3fA)A0E-_sYbC!Lm|#GEU>UuQ{H*TgZ4dTk_)zJHQ>j6uPn6Y2GHP2{A7PyY*#oixXRL3-8=6Bn0fRDm*PlkKT(MiWq4'
        'Me6*Sj|nLiv8m0orj$gB&02s)5mAG+*_at#F(^jZH&BM9<|b-&PeTXNNAhg0wS;H0@Ieahf}?b$0R>1!YjFkltB`RLj$z?GEX<O{'
        'm5S(1EBR@kyiq>pyT`P`$4R~VOwqES<<q;0T9sm@ysWJa&emXUmSCw?&st`Cd;{{0L}yoYTdpYv*W}qhnTi~8;ZnaAMgMhQQ@EX?'
        'klK=O%|@f$e`F8T7xl{e7uG&^>o}UN%dJt?8o89YX<d|E%0}GYv9N-9A|^!e<r}(CkV6U&^s>|>B?vg3qI)NOcR`Iua3T~^39R6T'
        '!r%`Q_YM70BA13i2GF2HrYBXt+*ZC(cL^NR<4QTu^=~DyA+FsZra_10Wea=dJ~O6oK!p%3575xFxwMrOk}qNVWcI^6#*iiFPF0p2'
        'xV)lT^E!)TYbH=YOFJZIWhcO8UqMdjk*a)#%BzO(5|$(wk$u{m5=S^mNuF*jRqoda!}~V|BhR*60i~~RWX>FChRko@_?X7G-N-Cx'
        'atr{agjv!k4R3QQXGuOST|(&011jaEBbiZxF32IT)0|KXx+_GHBlC*VYhi7lg`x&*158UNX>R3^Ne^EVv`1;w2TATm3O&t|Tp}AU'
        'MXtccIhRT#)+9`Ux;soo5!qrDqBb8z`%k8PE$FA!-`83KTsm4sip2@_Tg*-YItA^_DfpJEE2z9&aiPJ++ZA*gg3MLFdj~$Kif@+@'
        'RW{Fm>lbhxat3ev2Vb1h(t1q#30l9$3XC+Ahuo#{gVTIEs0c=@DD0F5s`ZX?HFyTV6mEo32fhJ{9c|ObCs}faWQ9|s6OvtpjbYhI'
        'EE}ZRD+`5~3rcY|j8tXJUL`XK=GJ5sZ`BoUV2Meh#(os_JNZOc66;fxgf;9;&BYQ~((PUZVc7Rt`%X2zVJw?PlFXsjvLYyDIu=dy'
        '^3`hbf2Yca`gcb~E3m!ML_8~Kh*{w{v8pKAPn-s>Hd?gEnF(B4oQI7x&9mveTZ<rAIQhv8^yM>gUQD-3L#g(ohiE@yE-+c=i+fDB'
        '5rE(rE_XUwAp0n;)8*ptVKf0^PA0t6(rj*KXim?~Lrmu_lqn_$=oIGu31Wutmy4v5c!F!RVn}~8QxczTAMIA#dUy%m315O6fS2Sy'
        'O6Bq;@^nK@%a_Q;TXPNN*z+awxx7Ttx+JW4k{S$2;;gL)1z#-YL2*+=hx|iTBGo{7BfI>w*tB85`hj3roI(p}K-CkVgK!6Cfk_jp'
        'o{0}(Bu|V#XQ=APw*&F8BR^~Mb|9Z;@m&1ZTr8RwBIUqP<1MlIvw}?<PUAz;{BmRCa?!kV>mv|7-Es*$O9^adp}NLAMe{DQZ>?y*'
        '%t1&dCdCU_vM&%Axdj5EyKWvVkt7p8DnagEFq+~2bBW`%4C|dRpjI6)*DNR|@!v@9FD3A|S_}{B$&<wY*_MXAV7B{2L4gZxQEXd)'
        'E!956OsZ+NE>T}m8vu(DUe@aU>d#nYvocGc2W`Gw_LnW0pefp|Dfm{1z_5Ud!;}%2pb7z_v+%2Stx8e7QEZ<!7Dv0@p;Cw*t^vul'
        '@iBL3sJ?qqat7LDPD0i~OL2FF_YD}SR7g%39@4=5o0b9r%{x26bth=u3b*V|*PT?>YyuHhfpA|g5H7z^1cI;KWG8cN!2}{K1YF!4'
        'WS8jHgjg$JUul2B#vmuu<~f;@Z-Xw8liD0{^U#Z*Zy3_gyFPzk_6S}+I4CsDF)$~{{Gn#`r{yo2J2c9`wOsE#_06P>Pjk>2jhf}~'
        '%IJ-9;Z+rVYRxG(NflL%L0<j%UIzwN1qo=_iec}u6*|aN>C#&VlI-iqpl}qDI3+`AT@@t<&*iSk=2Fr%zl{*70fMG%JZ!gceD<bd'
        'Yg?EVOv+TXhamTpZJ5k^F=Gp4<!MkXxXlYY+VH~eCh%m)KA2m&7hAO`xnx~iGXKqa{x9D8O(5IG(8=D)C7H{@l!q@ruorkyG_hcM'
        '1Fq@IE-mV}Itc&&FD>M$pr#_9T%0Bf|3`0j+((o25^zpb8&S$@45s6UP~sd@Q;cEENm@lk*tTA4dr%hPGKgoPuPfVPx0smIE8Ae1'
        '5-KWNYouZUVfAzngyj-f1e(bam7sf$)Uoaw!fTn6Q3=9x%~(Q@1^uWowEss1+G-ITnip)2u~#tNw&iXVSbVgIqb-vR;j;$pcVd*&'
        '8oYG7QB7?+<Zx%B$7>u^kw^|mTU+Yzg+;-;MPNm?-Gb!A>%tjFbd+&Dd*0~Td)?sfn`M?YbZEJIrM$F(nsI2K7E@c?sE=gKJ#Huy'
        '%ai52q1&k3jh!mrG3lyJb?iiG>aL9RVRVz&4CSPxx5LG$H?tqCdxuNQ2}Y-faHLVptwywjK4^&Nb7NzM2E5?FZ+T-Ro6GLRRF{O%'
        'ZhK=;$XGG8AgFFPT)sg&Cava_%t@&bLZUq88zEUdx;5{t*Nr+E7Bui=f+&4-s#RgJVP*3{mPY-85f~{{B1JtcS%5hmV}^calg&PN'
        'JI<iVjn9Bn7+um4EOe4q5y|PCS=g3+4^rBm?3oJ^5Uw<XFK4*Yb|&mjqczizUz0k{U#E_1z4t=>2kQ8dI&R4;-a2krcv4i5q^~s2'
        'GsTERdXZJbn#DRCMY@;eWgs;yB0XuDj|xfmW)*G2-nKGx@=3^BGI3|9(+V>5u+D31UZYBe*G%bJgvqiKlv|K<LRGQOyFlNex{xyi'
        'n2J?e<TAZ~vuwpRmgS%!E!%C(YB%JZw>sxi$H#4yy59{(Tb-~|r!>><G_$Rf_Uh!WtP!Zq8g_bm_vRZvN-O=Hir0BkO!8aP{?<gm'
        'HKDJbw^@E`-rqJEa7_<f69(PK<W^c=MDFrscVkw#zekZ?H(p!xbu6-;WntQGHV=8LjR}jWNZm0xc>T=fbu%-0VThHi6i(@F%tD^w'
        '-843*+~lF1wSB6jaW`U8ylkJ(K-{w2LP_6Ht`xp6E!W|%26VMV!<1ofrzo-Zu<8On&k8WTvlvk?n@S6=d=mdi<#eGep($h8lai=$'
        'op-A?p!CSN3@zjoCT7TrRr?6}t8QW3bPT9c;hQk8<{|sCZU;)!@15zr4f6b?&n+`lNudU-Ckszx=j`oU`NdJ;NYJ7JHu8BJK`l<!'
        'i3`RC)GzV38}rt>90kq>b5?kiMgP52TE9SP{eo8hV0)WVll%XNo&WpKs{9Vs(jQ2N^!!d6ZEm-+gv7}bmv%G6hAabmAeTrEi~ORu'
        't0^N8PA@b_WO8|Aur1oY-RXM5#^E|bk7A6AK>$lgx*-<UX6Fe_B~$t7$0<L_KU$K~P`#{13FStO&(vUiCywxHO$pMTnL<}6PONVd'
        'I?KcE=4}3RTFh?xu~tY}WU*;gahExd%mij~&f2#eCspKBj+;WKij*pLy6muO$TqGmJE1?Z_!E;d=8hTo>(1;@T)kv&W}EXTWWE|r'
        '9o81rHEMD)GdSYxXs5k=)VA;O{MN^^SM&RS)MhYwiX$D{475p+*_`y46Af{F%yD$wN7sDPv3+ye7fW0#(lNb|j+}*fOs;`ih)NUl'
        'MSV@)_{(@FX07)G{+?NNZrTdCnSINkBuuLXz93w4yB@0Q)=b7=szE|DypzHEg%?Tg1-n0C^jI+))12o;mTt_8KZIhLfOr)I2Fk?L'
        'hX);FQFnga#r~0)oF()PKZjJ-+DBTr(bL+El6bV<cva(DZj4OXXF4iu5?192xO;?0^|GDk?ZUL!%r<9sPaNK<ric@D88N%|KnG^L'
        '_6#=h6j@vo9i{ISge~@_-A~N(77NeGlL`Sgw)!{pzAXJVQr{_^GjiLN{v>?^D1g=!R%Pj)YLX7EJeKgBzSqx4nC3=jc`p=KEGgPK'
        'tg$N$4eM<-6&SP3c>6f9k6SMIQy%^5v~9s1!0uUbMEd`V1u~R2iA7Rj%%zh3m9wp52wpqNf+$kXd~vWB#~=G*)Ir2ZC;pndeL<s^'
        '4{}$A`DpviBUH_zT^|OMYet$e(y`9r!yk1)v8mSl&&4FEEvC&<zO$)mn4e9PNDCTrR<~ENyevjDdZl=)3f~nK(Gz90v2D_oRDizD'
        '0j(wXRDC9r<r0Enhj2X7gx^|fuX0bM5APVcy`c&u0;T#>sNT-^=xC26{#X#U4F2s~`9<xwkyfJrE%Mo|T+C3Z6DMi5ekligWLH<%'
        'Ja3K07u>RgV2pfVHm;e_b7MHAE$5nNOKx8Hcw{c~;4E!SsON3-R}*``#!#i2pjOV+9~6Y}hRC|L(av&Cv@QCW`z8x6eD`@6_%2$k'
        'A@*srz)qcTlkqaj*$r}hp_-}<tqkKE7LXfqieSzcR3^b>g8g-m=mga{`rqUYuG0)XCWz1sSM3x2{~c3<yV?5R3T#<|jLu_Z)GSAc'
        '(ODfxwK$}YHt<Gq*Z-tn2NcG*-(3#ib0!P^p0hhKR2G4)EdQl{=c~8f`1=ekUwr-e-Oqo`S(-9CmZigS^-j7(=V9>)$c04$!MXfF'
        '7uq0a!i@4`V5cS~Iv!dY!bMqu=ay&o%*i`}k-MV7gP27LTWvee7r9{kwiJhqz%>@J?Rk7vky$GkfgP=Y&Kh~lV6p;pL@&WpJUSIw'
        '=?#^8wgm6N62nU&-#!=h&XKF7gqTuB6g<`eJ$*UrfbT}fe&H=Oa;BLk3+>CeVYniYsDY1r+II|w0F)z`-Qpt8HUrmi*I?@A?sCvc'
        '>dh(7^CrfF)726fq&S-+y|Sab$P>pW*J{KcVs*DMwD&w%9NmM$y`A}kdGfuq<q#~sYihI7CblwR8v0v`@V0Ux$5x@u-a?O+ZPD{r'
        'F={^-5X3n6#C-z1AX~58%QKQc=RV18%Ax;YmO<OKa}MsimpQ3pe$ZLudCsqyX}MJp+yeXzm@Ck(?F#LH*qL%h^t}brrAOqvXfs5I'
        '-_DaxOo0as)np;z9P0GjtZCB}>S%SPgVhf6Wm4BDI~uPJmO9<>%!k8FfV}eOPZ$ZhT{8CT@+pL>oHnsY?U3`i^XR9&xTDmp6s}Zn'
        'YccJzH(Xl|%8<jmVLhwR*)ffA4TxHHxxyFcIb2gT7*}8{yVL!5`QO^AkuH18Nk@W<J|n0LLz=di(3)V@1|96kxb6IL%;bRT+F=uF'
        'a&6SU`bsW^$&NH6vCq;Q@;P*-uk`jc=A)*TxYBOleTVY;HEY#q9)zVKtIv6DX$FFn?$h7+qfv}y|E2WXC)@vi(eL`pz7}pyihj4E'
        'xoCxTiX&<mL8*IYI*MWW%7*NWN|UXP#lreV;kGev5|nci1K0Bv!<hH9!Y@w>1s?hQjYI#1I`)tGO#L@{rl0wlTdDw_7NZ?%r|7F?'
        'Y3|4NqVImIKFzgV;%;zP1RG1MNU_eZNaI1d!uy%DzHTJtn=Scgt%n;eK*z8l-~ufIgAcC``16m=goD^DZtkXVipJd1%`jUdPl~}%'
        '@GDf!jHZs)k13r;D52BnW<T&a*}y+w!@pM3&h6BV{1YR7fVw|OO>CDIG&0daWI>puNt~_m5g)QmKJNFvy;IpJ9Ys8v*?Dw-2t(pu'
        'X5qm$K+TbZ!|*2UNXs00`x752XO5<Cdh~CQi+}!wr)_9Z_;(1Rhx95_O~)X4ew7EDgZ?xI#GAl?iks2;Iv*<-%F*e(x48{Wx0b;)'
        '*tWDQhwU1wd7j~e2vB_Vhc%ei4Z}z2pv`d$?dBcz$RYo*2LJlX_%qK3{S^t?{67'
    ),
}


class BitmapFont:
    def __init__(self, spec):
        self.chars = spec["chars"]
        self.ascent = spec["ascent"]
        self.descent = spec["descent"]
        self.master = spec["master"]
        self.raw = zlib.decompress(base64.b85decode(spec["data"]))
        self.index = {ch: i for i, ch in enumerate(self.chars)}
        self.glyphs = []
        off = 0
        for (adv, w, h, xoff, yoff) in spec["glyphs"]:
            self.glyphs.append((adv, w, h, xoff, yoff, off))
            off += w * h
        self._cache = {}

    def _bit(self, g, x, y):
        _, w, _, _, _, off = g
        pos = off + y * w + x
        return (self.raw[pos // 8] >> (7 - pos % 8)) & 1

    def _scaled(self, ch, size):
        """Coverage map for one glyph at one size (cached)."""
        key = (ch, size)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        g = self.glyphs[self.index.get(ch, self.index["?"])]
        adv, w, h, xoff, yoff, _ = g
        scale = size / self.master
        if w == 0 or h == 0:
            res = (0, 0, int(round(adv * scale)), 0, 0, bytearray())
            self._cache[key] = res
            return res
        dw = max(1, int(round(w * scale)))
        dh = max(1, int(round(h * scale)))
        cov = bytearray(dw * dh)
        for j in range(dh):
            sy0 = j * h // dh
            sy1 = max(sy0 + 1, (j + 1) * h // dh)
            for i in range(dw):
                sx0 = i * w // dw
                sx1 = max(sx0 + 1, (i + 1) * w // dw)
                s = 0
                for yy in range(sy0, sy1):
                    for xx in range(sx0, sx1):
                        s += self._bit(g, xx, yy)
                area = (sx1 - sx0) * (sy1 - sy0)
                cov[j * dw + i] = (s * 255) // area
        res = (dw, dh, int(round(adv * scale)),
               int(round(xoff * scale)), int(round(yoff * scale)), cov)
        self._cache[key] = res
        return res

    def width(self, text, size):
        scale = size / self.master
        total = 0
        for ch in text:
            g = self.glyphs[self.index.get(ch, self.index["?"])]
            total += g[0]
        return int(round(total * scale))

    def line_height(self, size):
        return int(round((self.ascent + self.descent) * size / self.master))

    def draw(self, cv, x, baseline_y, text, size, color):
        """Draw text with its baseline at baseline_y; returns end x."""
        pen = x
        for ch in text:
            dw, dh, adv, xoff, yoff, cov = self._scaled(ch, size)
            if dw and dh:
                gx = pen + xoff
                gy = baseline_y + yoff
                for j in range(dh):
                    row = j * dw
                    for i in range(dw):
                        a = cov[row + i]
                        if a:
                            cv.blend(gx + i, gy + j, color, a)
            pen += adv
        return pen

    def draw_centred(self, cv, cx, baseline_y, text, size, color):
        self.draw(cv, cx - self.width(text, size) // 2, baseline_y, text, size, color)

    def draw_right(self, cv, x_right, baseline_y, text, size, color):
        self.draw(cv, x_right - self.width(text, size), baseline_y, text, size, color)


REG = BitmapFont(FONT_REG)
BOLD = BitmapFont(FONT_BOLD)


def wrap(text, font, size, max_w):
    lines = []
    cur = ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if font.width(trial, size) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_para(cv, x, baseline_y, text, font, size, color, max_w, leading):
    y = baseline_y
    for line in wrap(text, font, size, max_w):
        font.draw(cv, x, y, line, size, color)
        y += leading
    return y


# --- helpers ---------------------------------------------------------------
def alpha_circle(cv, cx, cy, r, color, a, clip=None):
    for dy in range(-r, r + 1):
        dx = int(math.sqrt(r * r - dy * dy))
        for x in range(cx - dx, cx + dx + 1):
            if clip is not None:
                ccx, ccy, cr = clip
                if (x - ccx) ** 2 + (cy + dy - ccy) ** 2 > cr * cr:
                    continue
            cv.blend(x, cy + dy, color, a)


def card(cv, x, y, w, h, r=10):
    cv.round_rect(x, y, w, h, r, CARD_LINE)
    cv.round_rect(x + 2, y + 2, w - 4, h - 4, r - 2, CARD)


def chip(cv, x, y, text, color):
    w = BOLD.width(text, 15) + 28
    cv.round_rect(x, y, w, 30, 15, (233, 229, 218))
    BOLD.draw(cv, x + 14, y + 21, text, 15, color)
    return x + w


# --- icons (drawn in a 46x46 box at x, y) ----------------------------------
def draw_flame(cv, x, y):
    cv.poly([(x + 8, y + 42), (x + 4, y + 30), (x + 12, y + 18),
             (x + 20, y + 10), (x + 24, y + 2), (x + 30, y + 12),
             (x + 38, y + 20), (x + 42, y + 32), (x + 36, y + 42)],
            (224, 110, 30))
    cv.poly([(x + 16, y + 40), (x + 14, y + 32), (x + 20, y + 24),
             (x + 24, y + 18), (x + 28, y + 26), (x + 34, y + 32),
             (x + 30, y + 40)], YELLOW)


def draw_ship(cv, x, y):
    cv.poly([(x + 4, y + 30), (x + 42, y + 30), (x + 36, y + 42),
             (x + 10, y + 42)], NAVY)
    cv.rect(x + 18, y + 18, 14, 12, INK)
    cv.line(x + 25, y + 18, x + 25, y + 8, INK, 2)
    cv.poly([(x + 25, y + 8), (x + 34, y + 11), (x + 25, y + 14)], RED)
    cv.polyline([(x + 0, y + 45), (x + 8, y + 43), (x + 16, y + 45),
                 (x + 24, y + 43), (x + 32, y + 45), (x + 40, y + 43),
                 (x + 46, y + 45)], OCEAN, 2)


def draw_scales(cv, x, y):
    cv.line(x + 23, y + 8, x + 23, y + 40, INK, 3)
    cv.line(x + 8, y + 12, x + 38, y + 12, INK, 3)
    cv.circle(x + 23, y + 9, 3, GOLD)
    cv.line(x + 10, y + 12, x + 5, y + 26, INK, 2)
    cv.line(x + 10, y + 12, x + 15, y + 26, INK, 2)
    cv.line(x + 36, y + 12, x + 31, y + 26, INK, 2)
    cv.line(x + 36, y + 12, x + 41, y + 26, INK, 2)
    cv.poly([(x + 3, y + 26), (x + 17, y + 26), (x + 10, y + 34)], GOLD)
    cv.poly([(x + 29, y + 26), (x + 43, y + 26), (x + 36, y + 34)], GOLD)
    cv.line(x + 14, y + 40, x + 32, y + 40, INK, 3)


def draw_trophy(cv, x, y):
    cv.ellipse_outline(x + 10, y + 14, 6, 8, GOLD, 3)
    cv.ellipse_outline(x + 36, y + 14, 6, 8, GOLD, 3)
    cv.poly([(x + 12, y + 6), (x + 34, y + 6), (x + 32, y + 24),
             (x + 26, y + 30), (x + 20, y + 30), (x + 14, y + 24)], GOLD)
    cv.rect(x + 21, y + 30, 4, 8, GOLD)
    cv.rect(x + 14, y + 38, 18, 6, (176, 141, 26))


# --- lead illustration -----------------------------------------------------
def draw_globe():
    """Earth with a crack through it, on a keyed temp canvas."""
    s = Canvas(340, 340, KEY)
    s.circle(170, 170, 128, OCEAN)
    alpha_circle(s, 128, 118, 72, (255, 255, 255), 26, clip=(170, 170, 126))
    alpha_circle(s, 150, 138, 48, (255, 255, 255), 18, clip=(170, 170, 126))
    # abstract continents
    s.poly([(95, 120), (130, 95), (165, 105), (150, 140), (115, 150), (95, 135)], LAND)
    s.poly([(210, 110), (250, 125), (265, 160), (240, 185), (215, 165), (205, 135)], LAND)
    s.poly([(120, 210), (170, 195), (215, 215), (190, 245), (140, 245)], LAND)
    s.poly([(250, 220), (268, 228), (258, 244), (242, 236)], LAND)
    s.poly([(225, 130), (250, 140), (245, 165), (222, 158)], LAND_DARK)
    # clouds
    alpha_circle(s, 118, 88, 16, (255, 255, 255), 70)
    alpha_circle(s, 242, 108, 13, (255, 255, 255), 70)
    # the crack: a jagged split down the planet
    s.polyline([(168, 48), (180, 80), (164, 115), (182, 150), (166, 185),
                (184, 220), (170, 255), (182, 292)], RED_DARK, 6)
    s.ring(170, 170, 128, 4, NAVY_DARK)
    return s


def draw_lead_art(cv):
    cv.blit_keyed(draw_globe(), 620, 116)
    # sun, top right
    cv.circle(930, 165, 28, YELLOW)
    for k in range(8):
        a = k * math.pi / 4
        cv.line(int(930 + 36 * math.cos(a)), int(165 + 36 * math.sin(a)),
                int(930 + 48 * math.cos(a)), int(165 + 48 * math.sin(a)),
                YELLOW, 3)
    # smokestacks, bottom left of the art
    cv.rect(636, 396, 18, 52, (90, 90, 90))
    cv.rect(662, 404, 18, 44, (110, 110, 110))
    cv.circle(645, 388, 7, (170, 170, 170))
    cv.circle(638, 376, 5, (190, 190, 190))
    cv.circle(652, 368, 4, (205, 205, 205))
    cv.circle(671, 396, 6, (170, 170, 170))
    cv.circle(676, 386, 4, (190, 190, 190))
    # oil derrick, bottom right
    cv.line(900, 448, 920, 400, INK, 3)
    cv.line(940, 448, 920, 400, INK, 3)
    cv.line(895, 448, 945, 448, INK, 3)
    cv.line(908, 428, 932, 428, INK, 2)
    cv.line(912, 414, 928, 414, INK, 2)
    cv.rect(916, 394, 8, 8, INK)
    # NO DEAL stamp over the globe's right edge
    cv.circle(905, 300, 58, CARD)
    cv.ring(905, 300, 62, 5, RED)
    cv.ring(905, 300, 52, 2, RED)
    BOLD.draw_centred(cv, 905, 284, "COP31", 13, RED)
    BOLD.draw_centred(cv, 905, 310, "NO DEAL", 21, RED)


# --- panels ----------------------------------------------------------------
PANELS = [
    ("INDONESIA", RED,
     "24 DEAD IN FACTORY FIRE",
     "A candy-factory blaze in Indonesia kills at least 24 people. "
     "Around 30 workers are still missing as rescuers search the ruins.",
     draw_flame),
    ("UKRAINE", (29, 78, 137),
     "WAR SPREADS TO LIBYA",
     "Kyiv says it sank a Russian warship off Libya and damaged a cargo "
     "vessel. Russian strikes on the Kyiv region kill several people.",
     draw_ship),
    ("THE HAGUE", (46, 107, 79),
     "MYANMAR GUILTY OF GENOCIDE",
     "The UN's top court rules Myanmar committed genocide against the "
     "Rohingya minority, in a landmark judgment at The Hague.",
     draw_scales),
    ("SPORT", (176, 141, 26),
     "ALCARAZ TAKES ATP FINALS",
     "A maiden title in Turin, beating Zverev. Gukesh begins his chess "
     "title defence against Sindarov in Geneva.",
     draw_trophy),
]


def draw_panel(cv, px, py, kicker, accent, headline, body, icon):
    card(cv, px, py, 470, 164)
    cv.rect(px, py + 12, 6, 140, accent)
    icon(cv, px + 22, py + 18)
    BOLD.draw(cv, px + 80, py + 40, kicker, 15, accent)
    BOLD.draw(cv, px + 22, py + 88, headline, 24, INK)
    draw_para(cv, px + 22, py + 116, body, REG, 16, BODY, 426, 20)


# --- the front page --------------------------------------------------------
def build_image():
    cv = Canvas(W, H, PAPER)

    # masthead
    cv.vgrad(0, 0, W, 96, NAVY, NAVY_DARK)
    BOLD.draw(cv, 28, 62, "THE WORLD IN ONE PICTURE", 36, CARD)
    REG.draw(cv, 28, 84, "THE DAY'S WORLD NEWS - IN A SINGLE IMAGE", 14, GOLD_LIGHT)
    BOLD.draw_right(cv, 996, 56, "TUESDAY 24 NOVEMBER 2026", 20, GOLD_LIGHT)
    cv.rect(0, 92, W, 4, GOLD)

    # lead story: COP31 collapses
    card(cv, 28, 112, 968, 384)
    BOLD.draw(cv, 56, 158, "CLIMATE \u00b7 ANTALYA, TURKIYE", 20, RED)
    BOLD.draw(cv, 56, 222, "COP31 COLLAPSES", 56, INK)
    BOLD.draw(cv, 56, 282, "WITH NO DEAL", 56, INK)
    draw_para(cv, 56, 320,
              "After two weeks of talks \u2014 the longest climate summit ever "
              "\u2014 nearly 200 nations walk away empty-handed. The two words "
              "that killed the pact: fossil fuels.",
              REG, 21, BODY, 520, 30)
    draw_lead_art(cv)
    x = 56
    for text, color in (("LONGEST COP EVER", INK),
                        ("NO FOSSIL-FUEL WORDING", RED),
                        ("US STAYED AWAY", INK),
                        ("1.5\u00b0C LIMIT AT RISK", RED)):
        x = chip(cv, x, 452, text, color) + 12

    # markets strip: Nvidia / Huang
    cv.round_rect(28, 512, 968, 64, 10, GREEN_DARK)
    BOLD.draw(cv, 52, 552, "MARKETS", 18, GOLD_LIGHT)
    BOLD.draw(cv, 176, 552, "NVIDIA +31% \u2014 HUANG IS BACK AS CEO", 21, CARD)
    cv.polyline([(670, 556), (681, 550), (691, 552), (704, 540), (716, 530)],
                GREEN_LINE, 3)
    cv.poly([(716, 528), (707, 530), (712, 538)], GREEN_LINE)
    BOLD.draw_right(cv, 972, 552, "~$1 TRILLION BACK", 20, GOLD_LIGHT)

    # four story panels
    for i, (kicker, accent, headline, body, icon) in enumerate(PANELS):
        px = 28 + (i % 2) * 498
        py = 592 + (i // 2) * 180
        draw_panel(cv, px, py, kicker, accent, headline, body, icon)

    # footer: also today + credit
    draw_para(cv, 28, 968,
              "ALSO TODAY \u2014 Settler arson in the West Bank condemned \u00b7 "
              "Denmark backs 'ghetto law' \u00b7 Waymo pulls driverless taxis "
              "off US freeways \u00b7 Boat capsizes off Senegal",
              REG, 15, BODY, 968, 20)
    REG.draw_centred(cv, 512, 1012,
                     "Compiled from the world news of Tuesday 24 November 2026",
                     14, BODY)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    cv = build_image()
    path = os.path.join(out_dir, "entry.png")
    size = write_png(cv, path)
    os.chmod(path, 0o644)
    print("wrote %s (%d bytes)" % (path, size))


if __name__ == "__main__":
    main()
