// ============================================================
//  显示器挂灯 · 3D 打印件（参数化模型）
//
//  用法：
//   1. 用 OpenSCAD 打开本文件，菜单「窗口 → 定制器（Customizer）」
//   2. 先填「铝槽尺寸」「显示器尺寸」（用卡尺量自己的实物）
//   3. 在「零件」里选要打印的零件，按 F6 渲染，再「文件 → 导出 → STL」
//   4. 正式打印前，先打三个「试配件」确认松紧，再调「打印配合」里的间隙
//
//  单位：毫米
//  坐标：X 朝后（显示器背面方向），Y 朝上，Z 沿灯体长度
//  每个零件导出时已经摆成推荐的打印方向，不需要支撑
// ============================================================

/* [零件] */
// 要导出的零件
part = "assembly"; // [assembly:装配预览（不用打印）, clamp:重力夹, saddle:灯体卡座, bay:电控仓, usb_cap:电控仓端盖（Type-C）, cap:右堵头, rail:背光导轨, diffuser:背光扩散条, test_plug:试配件-堵头插头, test_saddle:试配件-卡座, test_hinge:试配件-转轴]

/* [铝槽尺寸（买到后用卡尺量）] */
// 铝槽外宽（前后方向）
ch_w = 25;
// 铝槽外高（不含灯罩）
ch_h = 15;
// 铝槽侧壁厚
ch_wall = 1.2;
// 铝槽底板厚（贴灯带的那一面）
ch_floor = 1.5;
// 灯罩凸出铝槽开口的高度（平灯罩填 0）
cover_h = 3;
// 从开口往里，被灯罩卡扣占用的深度（插头会避开这一段）
cover_seat = 3;
// 铝槽长度（只影响装配预览）
ch_len = 450;

/* [显示器尺寸（用卡尺量）] */
// 显示器顶边往下 5 mm 处的厚度
mon_t_top = 15;
// 顶边往下「后臂长度」处的厚度（背面是斜的会更厚）
mon_t_low = 15;

/* [夹子] */
// 夹子宽度（沿灯体方向）
clamp_w = 30;
// 前挂钩往下盖住边框的深度（不要超过屏幕上边框宽度）
lip_drop = 5;
// 后臂长度（别碰到显示器背后的凸起）
arm_len = 40;
// 防滑垫厚度（硅胶垫或 TPU，不贴就填 0）
pad_t = 1;
// 后臂底部做配重仓
cw_pocket = true;
// 俯仰范围的中心偏置（度，正数 = 灯光朝人那一侧的余量更多）
tilt_bias = 8;
// 夹子在灯体上的位置（只影响装配预览，负数 = 往电控仓一侧偏）
clamp_pos = -30;

/* [电控仓] */
// 电控仓长度（零件塞不下就加大）
bay_len = 48;
// Type-C 开孔宽
usb_w = 9.4;
// Type-C 开孔高
usb_h = 3.8;

/* [背光导轨] */
// 每段长度（60 灯/米灯带 10 颗约 167 mm）
rail_len = 170;
// 背光朝后上方的角度
rail_angle = 35;
// 背光灯带宽度
strip_w = 10;

/* [打印配合] */
// 一般配合间隙（插头、卡座偏紧就加大 0.1，偏松就减小）
fit = 0.25;
// 转轴径向间隙（转动太松就改小，可以填负数；太紧就改大）
hinge_fit = 0.05;
// 卡座底部卡爪（灯罩边缘盖住铝槽侧壁时关掉）
saddle_lips = true;

/* [Hidden] */
$fn = 72;
eps = 0.01;
bw = 1.6;          // 打印件壁厚
st = 2.4;          // 卡座壁厚
plug_len = 8;      // 插进铝槽的长度
plug_wall = 1.4;   // 插头壁厚
face_t = 2.4;      // 堵头端面厚度
lip_t = 2.5;       // 前挂钩厚度
plate_t = 4;       // 夹子顶板厚度
arm_t = 4;         // 后臂厚度
cw_d = 12;         // 配重仓深度（朝后）
cw_h = 22;         // 配重仓高度
rr = 5;            // 转轴半径
coll_t = 3;        // 转轴套壁厚
web_w = 4.5;       // 连接筋宽度（靠近转轴处）
open_half = 55;    // 转轴套开口半角
cheek_t = 2;       // 转轴挡片厚度
r_out = 2;         // 外轮廓圆角

// ---------- 推导尺寸 ----------
gt = mon_t_top + 2*pad_t + fit;          // 夹口宽（顶部）
gl = mon_t_low + 2*pad_t + fit;          // 夹口宽（后臂底部）
R  = [-lip_t - 3.5, plate_t + 8];        // 转轴中心
Rh = rr + hinge_fit;                     // 转轴套内半径
Rc = Rh + coll_t;                        // 转轴套外半径
web_end = [-lip_t + 2, plate_t];         // 连接筋落在顶板上的位置
theta_w = atan2(web_end[1] - R[1], web_end[0] - R[0]);  // 连接筋方向
cx1 = R[0] - Rc + 2.5 - st - fit;        // 装配时铝槽后外壁的 X
cy0 = R[1] - 3;                          // 装配时铝槽开口的 Y
saddle_len = clamp_w - cheek_t - 0.3;    // 卡座长度（给挡片留间隙）
// 插头（插进铝槽）截面
px0 = ch_wall + fit;
px1 = ch_w - ch_wall - fit;
py0 = cover_seat;
py1 = ch_h - ch_floor - fit;
pin = [px0 + plug_wall, py0 + plug_wall, px1 - plug_wall, py1 - plug_wall];  // 插头内孔
// 电控仓腔体
cav = [bw, -cover_h + bw, ch_w - bw, ch_h - bw];
taper_h = max(pin[0] - cav[0], cav[2] - pin[2], pin[1] - cav[1], cav[3] - pin[3], 0) + 0.5;
key1 = bw + 5 + 1.5 + 8;   // 触摸键 1 中心（离电控仓外端）
key2 = key1 + 17;          // 触摸键 2 中心
// 俯仰范围（连接筋在转轴表面的角宽度）
web_half = asin(min(1, (web_w/2) / rr));
tilt_min = -(open_half - web_half) - tilt_bias;
tilt_max =  (open_half - web_half) - tilt_bias;

echo(str("夹口宽（顶部）= ", gt, " mm，（后臂底部）= ", gl, " mm"));
echo(str("俯仰范围约 ", round(tilt_min), "° 到 ", round(tilt_max), "°（负数 = 灯光朝人）"));
echo(str("整灯长度约 ", ch_len + bay_len + face_t * 2, " mm"));
if (key2 + 8.25 > bay_len - taper_h)
    echo("警告：bay_len 太短，触摸键 2 会碰到过渡段，请把 bay_len 加大");
if (px1 - px0 < 14 + 2 * plug_wall)
    echo("警告：铝槽内宽太窄，插头放不下灯带让位槽");

// ---------- 2D 工具 ----------
module rrect(x0, y0, x1, y1, r) {
    r2 = max(0, min(r, (x1 - x0)/2 - eps, (y1 - y0)/2 - eps));
    if (r2 > 0) translate([x0 + r2, y0 + r2]) offset(r = r2) square([x1 - x0 - 2*r2, y1 - y0 - 2*r2]);
    else translate([x0, y0]) square([x1 - x0, y1 - y0]);
}
module box2(b) translate([b[0], b[1]]) square([b[2] - b[0], b[3] - b[1]]);

// 堵头、电控仓的外轮廓 = 铝槽 + 灯罩
module end_profile() rrect(0, -cover_h, ch_w, ch_h, r_out);

// 插进铝槽的空心插头，顶部开槽给灯带和焊线让位
module plug_2d() difference() {
    box2([px0, py0, px1, py1]);
    box2(pin);
    translate([ch_w/2 - 7, pin[3] - eps]) square([14, plug_wall + 2*eps]);
}

// ---------- 右堵头 ----------
module cap() {
    linear_extrude(face_t) end_profile();
    translate([0, 0, face_t - eps]) linear_extrude(plug_len + eps) plug_2d();
}

// ---------- 电控仓（左端，装主控、电源件、两个触摸键） ----------
// 打印方向：外端朝下立着打印；Type-C 端盖从外端插入
module bay() {
    difference() {
        linear_extrude(bay_len) end_profile();
        // 主腔体（外端开口）
        translate([0, 0, -eps]) linear_extrude(bay_len - taper_h + 2*eps) box2(cav);
        // 45° 过渡到插头内孔，打印不用支撑
        hull() {
            translate([0, 0, bay_len - taper_h]) linear_extrude(eps) box2(cav);
            translate([0, 0, bay_len - eps]) linear_extrude(2*eps) box2(pin);
        }
        // 触摸键：顶壁内侧减薄到 1.0 mm，同时给 TTP223 模块定位
        for (k = [key1, key2])
            translate([ch_w/2 - 6.25, ch_h - bw - eps, k - 8.25]) cube([12.5, 0.6 + eps, 16.5]);
        // 触摸键图标（顶面浅刻 0.3 mm）：键 1 圆环，键 2 圆点
        translate([ch_w/2, ch_h - 0.3, key1]) rotate([-90, 0, 0])
            linear_extrude(0.3 + eps) difference() { circle(d = 7); circle(d = 5.4); }
        translate([ch_w/2, ch_h - 0.3, key2]) rotate([-90, 0, 0])
            linear_extrude(0.3 + eps) circle(d = 3.5);
        // 背光灯带出线孔（后壁）
        translate([ch_w - bw - 1, 2.5, bay_len - taper_h - 4]) rotate([0, 90, 0]) cylinder(d = 4, h = bw + 2);
    }
    translate([0, 0, bay_len - eps]) linear_extrude(plug_len + eps) plug_2d();
}

// ---------- 电控仓端盖（装 Type-C 母座） ----------
module usb_cap() {
    uy = (cav[1] + cav[3]) / 2;
    difference() {
        union() {
            linear_extrude(face_t) end_profile();
            translate([0, 0, face_t - eps]) linear_extrude(5 + eps) difference() {
                box2([cav[0] + fit, cav[1] + fit, cav[2] - fit, cav[3] - fit]);
                box2([cav[0] + fit + 1.2, cav[1] + fit + 1.2, cav[2] - fit - 1.2, cav[3] - fit - 1.2]);
            }
        }
        translate([0, 0, -eps]) linear_extrude(face_t + 2*eps)
            translate([ch_w/2, uy]) offset(r = 1) square([usb_w - 2, usb_h - 2], center = true);
    }
}

// ---------- 重力夹 ----------
// 打印方向：侧面朝下平放（整个零件是同一个截面拉伸出来的）
module clamp_2d() {
    offset(r = 0.6) offset(delta = -0.6) union() {
        translate([-lip_t, -lip_drop]) square([lip_t, lip_drop + plate_t]);                     // 前挂钩
        translate([-lip_t, 0]) square([lip_t + gt + arm_t, plate_t]);                           // 顶板
        polygon([[gt, plate_t], [gt + arm_t, plate_t], [gl + arm_t, -arm_len], [gl, -arm_len]]); // 后臂
        if (cw_pocket) translate([gl + arm_t - 0.5, -arm_len]) square([cw_d + 0.5, cw_h]);       // 配重仓
        hull() { translate(R) circle(d = web_w); translate([web_end[0] - 2, plate_t - 1]) square([4, 1]); } // 连接筋
        translate(R) circle(r = rr);                                                            // 转轴
    }
}
module clamp() {
    difference() {
        union() {
            translate([0, 0, -clamp_w/2]) linear_extrude(clamp_w) clamp_2d();
            // 转轴一端的挡片，防止灯体沿转轴滑出
            translate([R[0], R[1], -clamp_w/2]) cylinder(r = Rc - 0.5, h = cheek_t);
        }
        // 配重仓（开口朝上，塞螺母或钢珠后用热熔胶封口）
        if (cw_pocket)
            translate([gl + arm_t + 1.6, -arm_len + 1.6, -clamp_w/2 + 1.6]) cube([cw_d - 3.2, cw_h, clamp_w - 3.2]);
    }
}

// ---------- 灯体卡座（套在铝槽上，带转轴套） ----------
module saddle_u_2d() {
    x0 = cx1 - ch_w - fit;  x1 = cx1 + fit;
    y0 = cy0;              y1 = cy0 + ch_h + fit;
    lipd = saddle_lips ? 1.2 : 0;
    li = max(0.4, ch_wall - 0.2);
    difference() {
        rrect(x0 - st, y0 - lipd, x1 + st, y1 + st, 1.5);
        box2([x0, y0, x1, y1 + eps]);
        box2([x0 + li, y0 - lipd - eps, x1 - li, y0 + eps]);
    }
}
module collar_2d() {
    difference() {
        translate(R) circle(r = Rc);
        translate(R) circle(r = Rh);
        // 开口：让连接筋通过，开口大小决定俯仰范围
        translate(R) rotate(theta_w + tilt_bias) polygon([[0, 0],
            [2*Rc*cos(-open_half), 2*Rc*sin(-open_half)], [2*Rc, 0], [2*Rc*cos(open_half), 2*Rc*sin(open_half)]]);
    }
}
module saddle_2d() union() { saddle_u_2d(); collar_2d(); }
module saddle() linear_extrude(saddle_len) saddle_2d();

// ---------- 背光导轨（粘在铝槽后壁，灯带朝后上方） ----------
// 打印方向：贴铝槽的那一面朝下平放
module rail_2d() {
    a = rail_angle;
    sw = strip_w + 3;
    d = sw * sin(a) + 1.6;
    p1 = [d, 0];
    u = [-sin(a), cos(a)];
    n = [cos(a), sin(a)];
    p2 = p1 + sw * u;
    difference() {
        polygon([[0, 0], p1, p2, [0, p2[1]]]);
        polygon([p1 + 1.5*u - 1.8*n, p1 + (2.1 + strip_w)*u - 1.8*n, p1 + (2.1 + strip_w)*u + n, p1 + 1.5*u + n]);
    }
}
module rail() rotate([0, -90, 0]) linear_extrude(rail_len) rail_2d();
module diffuser() cube([strip_w + 3.2, rail_len, 0.8]);

// ---------- 试配件 ----------
module test_plug() {
    linear_extrude(1.2) end_profile();
    translate([0, 0, 1.2 - eps]) linear_extrude(6 + eps) plug_2d();
}
module test_saddle() linear_extrude(6) saddle_u_2d();
module test_hinge() {
    // 一截转轴（带连接筋）和一截转轴套，套上去转一转试松紧
    linear_extrude(8) intersection() { clamp_2d(); translate(R) circle(r = Rc + 5); }
    translate([-26, 0, 0]) linear_extrude(8) union() {
        collar_2d();
        translate(R) translate([-Rc - 6, -2]) square([7, 4]);   // 拨片
    }
}

// ---------- 装配预览 ----------
module assembly() {
    // 卡座在铝槽坐标里的起止位置（背光导轨避开这一段）
    s0 = clamp_pos + ch_len/2 - clamp_w/2;
    s1 = clamp_pos + ch_len/2 + clamp_w/2;
    // 显示器（深灰）
    color("#2b2f36") translate([pad_t + fit/2, -120, -330]) cube([mon_t_top, 120, 660]);
    // 重力夹
    color("#d6dbe1") translate([0, 0, clamp_pos]) clamp();
    // 卡座
    color("#8db0d6") translate([0, 0, clamp_pos - clamp_w/2 + cheek_t + 0.3]) saddle();
    // 铝槽及其上的零件（铝槽自己的坐标：X 0 = 前壁，Y 0 = 开口）
    translate([cx1 - ch_w, cy0, -ch_len/2]) {
        color("#b7bcc3") linear_extrude(ch_len) difference() {
            square([ch_w, ch_h]);
            translate([ch_wall, -eps]) square([ch_w - 2*ch_wall, ch_h - ch_floor + eps]);
        }
        color("#f3efe6") linear_extrude(ch_len) translate([ch_wall, -cover_h]) square([ch_w - 2*ch_wall, cover_h + 0.5]);
        color("#eceef1") translate([0, 0, -bay_len]) bay();
        color("#c9ced4") translate([0, 0, -bay_len - face_t]) usb_cap();
        color("#eceef1") translate([0, 0, ch_len + face_t]) mirror([0, 0, 1]) cap();
        for (z = [s0 - 4 - rail_len, s1 + 4])
            color("#f7f7f7") translate([ch_w, 0, z]) linear_extrude(rail_len) rail_2d();
    }
}

// ---------- 输出 ----------
if (part == "assembly") assembly();
else if (part == "clamp") translate([0, 0, clamp_w/2]) clamp();
else if (part == "saddle") saddle();
else if (part == "bay") bay();
else if (part == "usb_cap") usb_cap();
else if (part == "cap") cap();
else if (part == "rail") rail();
else if (part == "diffuser") diffuser();
else if (part == "test_plug") test_plug();
else if (part == "test_saddle") test_saddle();
else if (part == "test_hinge") test_hinge();
