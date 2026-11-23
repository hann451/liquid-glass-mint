require 'cairo'
pcall(require, 'cairo_xlib')

local WEATHER_TSV = '__USER_HOME__/.cache/liquid-glass/weather.tsv'
local STATUS_TSV  = '__USER_HOME__/.cache/liquid-glass/status.tsv'
local ALBUM_ART   = '__USER_HOME__/.cache/liquid-glass/album_art.png'

local function read_tsv(path)
    local t = {}
    local f = io.open(path, 'r')
    if not f then return t end
    for line in f:lines() do
        local k, v = line:match("^([^\t]+)\t(.*)$")
        if k then t[k] = v end
    end
    f:close()
    return t
end

local function utf8_trunc(s, max_chars)
    if not s or s == "" then return "" end
    local count = 0
    local bytes = 0
    for ch in s:gmatch("[%z\1-\127\194-\244][\128-\191]*") do
        count = count + 1
        if count > max_chars then
            return s:sub(1, bytes) .. "…"
        end
        bytes = bytes + #ch
    end
    return s
end

local function rounded_rect(cr, x, y, w, h, r)
    local rad = math.min(r, w / 2, h / 2)
    cairo_new_sub_path(cr)
    cairo_arc(cr, x + w - rad, y + rad, rad, -math.pi / 2, 0)
    cairo_arc(cr, x + w - rad, y + h - rad, rad, 0, math.pi / 2)
    cairo_arc(cr, x + rad, y + h - rad, rad, math.pi / 2, math.pi)
    cairo_arc(cr, x + rad, y + rad, rad, math.pi, 3 * math.pi / 2)
    cairo_close_path(cr)
end

local function draw_glass_card(cr, x, y, w, h, r)
    -- Soft outer shadow
    rounded_rect(cr, x, y + 4, w, h, r)
    cairo_set_source_rgba(cr, 0, 0, 0, 0.28)
    cairo_fill(cr)

    -- Frosted liquid glass body
    rounded_rect(cr, x, y, w, h, r)
    cairo_set_source_rgba(cr, 38/255, 52/255, 82/255, 0.44)
    cairo_fill_preserve(cr)

    -- Upper specular highlight gradient
    local grad = cairo_pattern_create_linear(x, y, x, y + h * 0.55)
    cairo_pattern_add_color_stop_rgba(grad, 0.0, 1, 1, 1, 0.18)
    cairo_pattern_add_color_stop_rgba(grad, 1.0, 1, 1, 1, 0.02)
    cairo_set_source(cr, grad)
    cairo_fill_preserve(cr)
    cairo_pattern_destroy(grad)

    -- 1.2px glossy white rim
    cairo_set_line_width(cr, 1.2)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.36)
    cairo_stroke(cr)
end

local function draw_text(cr, x, y, text, font, size, bold, r, g, b, a)
    cairo_select_font_face(cr, font, CAIRO_FONT_SLANT_NORMAL,
        bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(cr, size)
    cairo_set_source_rgba(cr, r, g, b, a)
    cairo_move_to(cr, x, y)
    cairo_show_text(cr, text)
end

local function draw_text_right(cr, right_x, y, text, font, size, bold, r, g, b, a)
    cairo_select_font_face(cr, font, CAIRO_FONT_SLANT_NORMAL,
        bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(cr, size)
    local ext = cairo_text_extents_t:create()
    tolua.takeownership(ext)
    cairo_text_extents(cr, text, ext)
    cairo_set_source_rgba(cr, r, g, b, a)
    cairo_move_to(cr, right_x - ext.width - ext.x_bearing, y)
    cairo_show_text(cr, text)
end

local function draw_text_center(cr, center_x, y, text, font, size, bold, r, g, b, a)
    cairo_select_font_face(cr, font, CAIRO_FONT_SLANT_NORMAL,
        bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(cr, size)
    local ext = cairo_text_extents_t:create()
    tolua.takeownership(ext)
    cairo_text_extents(cr, text, ext)
    cairo_set_source_rgba(cr, r, g, b, a)
    cairo_move_to(cr, center_x - ext.width / 2 - ext.x_bearing, y)
    cairo_show_text(cr, text)
end

local function text_width(cr, text, font, size, bold)
    cairo_select_font_face(cr, font, CAIRO_FONT_SLANT_NORMAL,
        bold and CAIRO_FONT_WEIGHT_BOLD or CAIRO_FONT_WEIGHT_NORMAL)
    cairo_set_font_size(cr, size)
    local ext = cairo_text_extents_t:create()
    tolua.takeownership(ext)
    cairo_text_extents(cr, text, ext)
    return ext.width
end

local function draw_weather_glyph(cr, cx, cy, kind)
    cairo_save(cr)
    cairo_translate(cr, cx, cy)
    if kind == "sun" then
        cairo_arc(cr, 0, 0, 5.2, 0, 2 * math.pi)
        cairo_set_source_rgba(cr, 1, 1, 1, 0.94)
        cairo_fill(cr)
        cairo_set_line_width(cr, 1.4)
        for i = 0, 7 do
            local a = i * math.pi / 4
            cairo_move_to(cr, math.cos(a) * 7.2, math.sin(a) * 7.2)
            cairo_line_to(cr, math.cos(a) * 9.5, math.sin(a) * 9.5)
        end
        cairo_stroke(cr)
    elseif kind == "partly" then
        cairo_arc(cr, -3.5, -2.5, 4.0, 0, 2 * math.pi)
        cairo_set_source_rgba(cr, 1.0, 0.86, 0.42, 0.95)
        cairo_fill(cr)
        rounded_rect(cr, -7, -0.5, 14.5, 6.2, 3.1)
        cairo_set_source_rgba(cr, 1, 1, 1, 0.92)
        cairo_fill(cr)
    elseif kind == "rain" then
        rounded_rect(cr, -7.5, -5.5, 15, 6.5, 3.2)
        cairo_set_source_rgba(cr, 0.85, 0.92, 1.0, 0.92)
        cairo_fill(cr)
        cairo_set_line_width(cr, 1.4)
        cairo_set_source_rgba(cr, 0.48, 0.84, 1.0, 0.96)
        cairo_move_to(cr, -3.5, 3.0); cairo_line_to(cr, -5.0, 7.0)
        cairo_move_to(cr, 0.5, 3.0);  cairo_line_to(cr, -1.0, 7.0)
        cairo_move_to(cr, 4.5, 3.0);  cairo_line_to(cr, 3.0, 7.0)
        cairo_stroke(cr)
    elseif kind == "snow" then
        rounded_rect(cr, -7.5, -5.5, 15, 6.5, 3.2)
        cairo_set_source_rgba(cr, 0.92, 0.96, 1.0, 0.94)
        cairo_fill(cr)
        cairo_arc(cr, -3.5, 5.0, 1.3, 0, 2 * math.pi); cairo_fill(cr)
        cairo_arc(cr, 0.5, 6.2, 1.3, 0, 2 * math.pi); cairo_fill(cr)
        cairo_arc(cr, 4.5, 5.0, 1.3, 0, 2 * math.pi); cairo_fill(cr)
    elseif kind == "storm" then
        rounded_rect(cr, -7.5, -5.5, 15, 6.5, 3.2)
        cairo_set_source_rgba(cr, 0.72, 0.78, 0.90, 0.92)
        cairo_fill(cr)
        cairo_set_line_width(cr, 1.6)
        cairo_set_source_rgba(cr, 1.0, 0.85, 0.28, 0.98)
        cairo_move_to(cr, 1.0, 2.0); cairo_line_to(cr, -2.0, 5.0)
        cairo_line_to(cr, 0.8, 5.0); cairo_line_to(cr, -1.5, 8.5)
        cairo_stroke(cr)
    else
        rounded_rect(cr, -7.5, -3.0, 15, 6.8, 3.4)
        cairo_set_source_rgba(cr, 0.92, 0.95, 1.0, 0.90)
        cairo_fill(cr)
    end
    cairo_restore(cr)
end

local function draw_bar(cr, x, y, w, h, pct, r, g, b)
    local p = math.max(0, math.min(100, tonumber(pct) or 0))
    rounded_rect(cr, x, y, w, h, h / 2)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.16)
    cairo_fill(cr)

    if p > 0 then
        local fw = math.max(h, w * (p / 100.0))
        rounded_rect(cr, x, y, fw, h, h / 2)
        cairo_set_source_rgba(cr, r, g, b, 0.94)
        cairo_fill(cr)
    end
end

function conky_main()
    if conky_window == nil then return end
    local cs = cairo_xlib_surface_create(
        conky_window.display,
        conky_window.drawable,
        conky_window.visual,
        conky_window.width,
        conky_window.height
    )
    local cr = cairo_create(cs)

    local weather = read_tsv(WEATHER_TSV)
    local status  = read_tsv(STATUS_TSV)

    local card_x  = 4
    local card_w  = 296
    local pad     = 20
    local inner_w = card_w - pad * 2
    local font_ui = "Noto Sans CJK JP"

    -- =========================================================================
    -- CARD 1: Clock, English Date & Weather (Centered, Mockup 1:1)
    -- =========================================================================
    local c1_y, c1_h = 4, 218
    draw_glass_card(cr, card_x, c1_y, card_w, c1_h, 22)

    local cx = card_x + card_w / 2
    local time_str = os.date("%H:%M")
    local date_str = os.date("%a, %b %d")

    draw_text_center(cr, cx, c1_y + 90, time_str, font_ui, 54, false, 1, 1, 1, 0.97)
    draw_text_center(cr, cx, c1_y + 124, date_str, font_ui, 17, false, 0.94, 0.96, 1.0, 0.90)

    local w_str = string.format("%s°C %s", weather.temp_c or "--", weather.condition or "晴れ")
    local tw = text_width(cr, w_str, font_ui, 16, false)
    local glyph_gap = 24
    local start_x = cx - (glyph_gap + tw) / 2
    draw_weather_glyph(cr, start_x + 8, c1_y + 169, weather.icon or "sun")
    draw_text(cr, start_x + glyph_gap, c1_y + 175, w_str, font_ui, 16, false, 0.95, 0.97, 1.0, 0.92)

    -- =========================================================================
    -- CARD 2: SYSTEM STATUS (CPU / RAM / SSD / 温度)
    -- =========================================================================
    local c2_y, c2_h = 244, 256
    draw_glass_card(cr, card_x, c2_y, card_w, c2_h, 22)

    draw_text(cr, card_x + pad, c2_y + 36, "SYSTEM STATUS", font_ui, 15.5, true, 0.96, 0.98, 1.0, 0.94)

    local cpu_pct  = tonumber(status.cpu_pct) or 0
    local mem_pct  = tonumber(status.mem_pct) or 0
    local disk_pct = tonumber(status.disk_pct) or 0
    local temp_num = tonumber(status.cpu_temp)
    local temp_pct = temp_num and math.max(5, math.min(100, ((temp_num - 20) / 75.0) * 100)) or 0
    local temp_str = (status.cpu_temp or "--") .. "°C"

    local rows = {
        { label = "CPU",  val = string.format("%d%%", cpu_pct),  pct = cpu_pct,  r = 0.39, g = 0.82, b = 1.0 },
        { label = "RAM",  val = string.format("%d%%", mem_pct),  pct = mem_pct,  r = 0.39, g = 0.82, b = 1.0 },
        { label = "SSD",  val = string.format("%d%%", disk_pct), pct = disk_pct, r = 0.39, g = 0.82, b = 1.0 },
        { label = "温度", val = temp_str,                        pct = temp_pct, r = 0.96, g = 0.65, b = 0.35 },
    }

    for idx, row in ipairs(rows) do
        local ry = c2_y + 74 + (idx - 1) * 46
        draw_text(cr, card_x + pad, ry, row.label, font_ui, 14, false, 0.95, 0.97, 1.0, 0.92)
        draw_text_right(cr, card_x + card_w - pad, ry, row.val, font_ui, 14, false, 0.95, 0.97, 1.0, 0.92)
        draw_bar(cr, card_x + pad, ry + 11, inner_w, 6, row.pct, row.r, row.g, row.b)
    end

    -- =========================================================================
    -- CARD 3: NOW PLAYING (YouTube / YouTube Music MPRIS + Thumbnail)
    -- =========================================================================
    local c3_y, c3_h = 522, 210
    draw_glass_card(cr, card_x, c3_y, card_w, c3_h, 22)

    draw_text(cr, card_x + pad, c3_y + 36, "NOW PLAYING", font_ui, 15.5, true, 0.96, 0.98, 1.0, 0.94)

    local ax = card_x + pad
    local ay = c3_y + 56
    local asize = 64

    cairo_save(cr)
    rounded_rect(cr, ax, ay, asize, asize, 12)
    cairo_clip(cr)
    local drew_art = false
    if status.media_art_ready == "1" then
        local img = cairo_image_surface_create_from_png(ALBUM_ART)
        if img and cairo_surface_status(img) == 0 then
            local iw = cairo_image_surface_get_width(img)
            local ih = cairo_image_surface_get_height(img)
            if iw > 0 and ih > 0 then
                cairo_save(cr)
                cairo_translate(cr, ax, ay)
                cairo_scale(cr, asize / iw, asize / ih)
                cairo_set_source_surface(cr, img, 0, 0)
                cairo_paint(cr)
                cairo_restore(cr)
                drew_art = true
            end
        end
        if img then cairo_surface_destroy(img) end
    end
    if not drew_art then
        local ag = cairo_pattern_create_linear(ax, ay, ax + asize, ay + asize)
        cairo_pattern_add_color_stop_rgba(ag, 0.0, 0.28, 0.44, 0.72, 0.85)
        cairo_pattern_add_color_stop_rgba(ag, 1.0, 0.56, 0.30, 0.58, 0.85)
        cairo_set_source(cr, ag)
        cairo_paint(cr)
        cairo_pattern_destroy(ag)

        -- Subtle play triangle
        cairo_move_to(cr, ax + 25, ay + 20)
        cairo_line_to(cr, ax + 46, ay + 32)
        cairo_line_to(cr, ax + 25, ay + 44)
        cairo_close_path(cr)
        cairo_set_source_rgba(cr, 1, 1, 1, 0.88)
        cairo_fill(cr)
    end
    cairo_restore(cr)

    -- Subtle inner border around artwork
    rounded_rect(cr, ax, ay, asize, asize, 12)
    cairo_set_line_width(cr, 1.0)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.25)
    cairo_stroke(cr)

    local m_title  = utf8_trunc(status.media_title or "YouTube で再生", 13)
    local m_artist = utf8_trunc(status.media_artist or "Chrome再生と自動連携", 18)
    draw_text(cr, ax + asize + 16, ay + 28, m_title, font_ui, 15, true, 1, 1, 1, 0.96)
    draw_text(cr, ax + asize + 16, ay + 50, m_artist, font_ui, 12.5, false, 0.85, 0.90, 0.98, 0.82)

    -- Scrubber bar with circular thumb
    local px = card_x + pad
    local py = c3_y + 166
    local pw = inner_w
    local ph = 3.5
    local prog = tonumber(status.media_progress) or 0.0
    prog = math.max(0.0, math.min(1.0, prog))

    rounded_rect(cr, px, py, pw, ph, ph / 2)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.24)
    cairo_fill(cr)

    local knob_x = px + pw * prog
    if prog > 0.0 then
        rounded_rect(cr, px, py, math.max(ph, pw * prog), ph, ph / 2)
        cairo_set_source_rgba(cr, 1, 1, 1, 0.88)
        cairo_fill(cr)
    end

    cairo_arc(cr, knob_x, py + ph / 2, 5.5, 0, 2 * math.pi)
    cairo_set_source_rgba(cr, 1, 1, 1, 0.96)
    cairo_fill(cr)

    cairo_destroy(cr)
    cairo_surface_destroy(cs)
end
