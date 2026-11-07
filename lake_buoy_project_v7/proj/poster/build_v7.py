"""Fill the LAKE 2026 36x48 in template (perceptualpewter_36x48.pptx) with the buoy-data poster."""
import copy, math, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from lxml import etree

SRC = '/mnt/user-data/uploads/perceptualpewter_36x48.pptx'
OUT = '/home/claude/proj/poster/lake2026_poster_v7.pptx'
FIG = '/home/claude/proj/figures/p_'
prs = Presentation(SRC)
slide = prs.slides[0]
sp = slide.shapes
by_name = {s.name: s for s in sp}
MINT, AMBER, WHITE, DARK, TEAL, SLATE, RUST, LTEAL, LGREY = '22313F', '0B6E7A', 'FFFFFF', '1C2733', '1B8A9A', '2E4053', 'A93226', 'E4F2F4', 'EEF1F5'
rgb = lambda h: RGBColor.from_string(h)
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'


def inch(v): return Emu(int(v * 914400))


def remove(shape): shape._element.getparent().remove(shape._element)


# ---------- text helpers ----------
def est_lines(text, size, width, indent=0.0, factor=0.50):
    cpl = max(8, (width - indent) / (factor * size / 72.0))
    return sum(max(1, math.ceil(len(part) / cpl)) for part in text.split('\n'))


def est_h(paras, size, width, spacing=1.17):
    h = 0
    for p in paras:
        t = ''.join(r[0] for r in p['runs']); sz = p.get('size', size)
        h += est_lines(t, sz, width, 0.32 if p.get('bullet') else 0) * sz * spacing / 72.0 + p.get('after', 0) / 72.0
    return h


def add_text(x, y, w, paras, size=22, color=MINT, h=None, font='Calibri', anchor=MSO_ANCHOR.TOP, align=None):
    if h is None: h = est_h(paras, size, w) + 0.05
    tb = sp.add_textbox(inch(x), inch(y), inch(w), inch(h)); tf = tb.text_frame; tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0; tf.vertical_anchor = anchor
    for i, p in enumerate(paras):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        if p.get('after') is not None: para.space_after = Pt(p['after'])
        if p.get('align') or align: para.alignment = p.get('align') or align
        for text, o in p['runs']:
            r = para.add_run(); r.text = text; f = r.font; f.name = font; f.size = Pt(o.get('size', p.get('size', size)))
            f.bold = o.get('bold', False); f.italic = o.get('italic', False); f.color.rgb = rgb(o.get('color', p.get('color', color)))
        if p.get('bullet'):
            pPr = para._p.get_or_add_pPr(); pPr.set('marL', str(int(0.32 * 914400))); pPr.set('indent', str(-int(0.32 * 914400)))
            bf = etree.SubElement(pPr, '{%s}buFont' % A); bf.set('typeface', 'Arial')
            bc = etree.SubElement(pPr, '{%s}buChar' % A); bc.set('char', '•')
    return tb, h


def P(text, **k): return dict(runs=[(text, {})], **k)


def PB(parts, **k):
    runs = [(t, o) for t, o in parts]; return dict(runs=runs, **k)


def B(text, **k): return dict(runs=[(text, {})], bullet=True, after=k.pop('after', 6), **k)


def BB(parts, **k): return dict(runs=parts, bullet=True, after=k.pop('after', 6), **k)


def card(x, y, w, h, fill=WHITE, radius=0.06, line=None):
    s = sp.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(x), inch(y), inch(w), inch(h)); s.adjustments[0] = radius
    s.fill.solid(); s.fill.fore_color.rgb = rgb(fill)
    if line: s.line.color.rgb = rgb(line); s.line.width = Pt(2)
    else: s.line.fill.background()
    s.shadow.inherit = False; return s


def picture(name, x, y, w, pad=0.14):
    from PIL import Image
    im = Image.open(FIG + name); h = w * im.height / im.width
    card(x, y, w + 2 * pad, h + 2 * pad); sp.add_picture(FIG + name, inch(x + pad), inch(y + pad), inch(w), inch(h)); return h + 2 * pad


def shape_text(shape, text, size, color=WHITE, bold=True):
    tf = shape.text_frame; tf.word_wrap = True; tf.margin_left = tf.margin_right = inch(0.08); tf.margin_top = tf.margin_bottom = inch(0.04)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE; p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
    r = p.add_run(); r.text = text; r.font.size = Pt(size); r.font.bold = bold; r.font.name = 'Calibri'; r.font.color.rgb = rgb(color)


def table(x, y, colw, rows, size=17, head_fill=TEAL, row_fills=None, bold_first_col=False, row_h=None):
    nr, nc = len(rows), len(colw)
    heights = []
    for r in rows:
        lines = max(est_lines(c, size, colw[j] - 0.2, 0, 0.5) for j, c in enumerate(r)); heights.append(lines * size * 1.15 / 72 + 0.16)
    if row_h: heights = [max(h, row_h) for h in heights]
    gs = sp.add_table(nr, nc, inch(x), inch(y), inch(sum(colw)), inch(sum(heights)))
    t = gs.table
    for j, wc in enumerate(colw): t.columns[j].width = inch(wc)
    for i, r in enumerate(rows):
        t.rows[i].height = inch(heights[i])
        for j, txt in enumerate(r):
            c = t.cell(i, j); c.margin_left = c.margin_right = inch(0.1); c.margin_top = c.margin_bottom = inch(0.04); c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.fill.solid(); c.fill.fore_color.rgb = rgb(head_fill if i == 0 else (row_fills[i - 1] if row_fills else (WHITE if i % 2 else LGREY)))
            tf = c.text_frame; tf.word_wrap = True; p = tf.paragraphs[0]; run = p.add_run(); run.text = txt
            run.font.size = Pt(size); run.font.name = 'Calibri'; run.font.bold = (i == 0) or (bold_first_col and j == 0)
            run.font.color.rgb = rgb(WHITE if i == 0 else DARK)
    return sum(heights)


# ---------- header ----------
def set_runs(shape, lines):
    tf = shape.text_frame
    for p in list(tf.paragraphs)[1:]: p._p.getparent().remove(p._p)
    for i, (txt, size, bold, color) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        for r in list(p.runs): r._r.getparent().remove(r._r)
        p.alignment = PP_ALIGN.CENTER
        for k, part in enumerate(txt.split('~')):
            if k: p.add_line_break()
            r = p.add_run(); r.text = part; r.font.size = Pt(size); r.font.bold = bold; r.font.name = 'Calibri'; r.font.color.rgb = rgb(color)
        if i: p.space_before = Pt(6)


title_box, auth_box = by_name['TextBox 88'], by_name['TextBox 89']
title_box.top = inch(0.70); title_box.height = inch(2.4)
set_runs(title_box, [('LAKE 2026: 15TH BIENNIAL LAKE CONFERENCE', 22, True, 'D7E6F5'),
                     ('A Secure Cloud-Based Framework for Smart Lake Water-Quality~Monitoring and Anomaly Detection', 40, True, 'FFFFFF')])
auth_box.top = inch(3.35); auth_box.height = inch(2.5)
set_runs(auth_box, [('Mannat Tomar', 30, True, 'FFFFFF'),
                    ('BCA (Hons.) Data Science, Minor in Cybersecurity, Chanakya University, Devanahalli, Bengaluru', 24, False, 'D7E6F5'),
                    ('mannatt.bca23@chanakyauniversity.edu.in | Bengaluru, Karnataka | 18–20 November 2026 | www.lake2026conference.in', 22, False, 'C8DCEB'),
                    ('Theme: IoT Buoys, Real-time Sensor Networks & Hydrological Monitoring', 22, False, 'C8DCEB')])

# ---------- section boxes: reposition template shapes ----------
SEC = {  # key: (rect, heading, body, bar)
    'abstract': ('Rounded Rectangle 75', 'TextBox 83', 'TextBox 84', None),
    'intro': ('Rounded Rectangle 76', 'TextBox 27', 'TextBox 28', None),
    'results': ('Rounded Rectangle 77', 'TextBox 36', 'TextBox 37', None),
    'concl': ('Rounded Rectangle 79', 'TextBox 39', 'TextBox 40', None),
    'ack': ('Rounded Rectangle 78', 'TextBox 42', 'TextBox 43', None),
}
bars = [s for s in sp if s.name.startswith('Rectangle: Rounded Cor')]
bar_of = {}
heads = {'abstract': 'TextBox 83', 'intro': 'TextBox 27', 'results': 'TextBox 36', 'concl': 'TextBox 39', 'ack': 'TextBox 42'}
for k, (rn, hn, bn, _) in SEC.items():
    hd = by_name[hn]
    bar_of[k] = min(bars, key=lambda b: abs(b.top - (hd.top + inch(0.72))) + abs(b.left - (hd.left + inch(0.15))))
    remove(by_name[bn])


def place(key, x, y, w, h, title=None):
    rn, hn = SEC[key][0], SEC[key][1]
    r, hd, bar = by_name[rn], by_name[hn], bar_of[key]
    r.left, r.top, r.width, r.height = inch(x), inch(y), inch(w), inch(h)
    hd.left, hd.top, hd.width = inch(x + 0.47), inch(y + 0.43), inch(w - 0.94)
    bar.left, bar.top = inch(x + 0.62), inch(y + 1.15)
    if title:
        hd.text_frame.paragraphs[0].runs[0].text = title


def clone_box(src_key, new_key, title):
    new = {}
    for part, nm in zip(('rect', 'head', 'bar'), (SEC[src_key][0], SEC[src_key][1], None)):
        el = by_name[nm]._element if nm else bar_of[src_key]._element
        c = copy.deepcopy(el); sp._spTree.append(c); new[part] = c
    ids = [int(e.get('id')) for e in slide.shapes._spTree.iter() if e.tag.endswith('}cNvPr')]
    nid = max(ids) + 1
    for c in new.values():
        for e in c.iter():
            if e.tag.endswith('}cNvPr'): e.set('id', str(nid)); e.set('name', f'{new_key}-{nid}'); nid += 1
    shapes = {s.name: s for s in sp}
    names = [e.find('.//{*}cNvPr').get('name') for e in new.values()]
    rect, head, bar = [shapes[n] for n in names]
    head.text_frame.paragraphs[0].runs[0].text = title
    nk = new_key; SEC[nk] = (rect.name, head.name, None, None); by_name[rect.name] = rect; by_name[head.name] = head; bar_of[nk] = bar
    return nk


clone_box('intro', 'datameth', 'Data and Methods')
clone_box('results', 'secure', 'Cybersecurity and Pipeline')
LX, RX, BW = 0.63, 18.32, 17.0
_h = by_name['Rounded Rectangle 74']; _h.fill.gradient(); _h.fill.gradient_angle = 0
_h.fill.gradient_stops[0].color.rgb = rgb('15304A'); _h.fill.gradient_stops[1].color.rgb = rgb('2F7F94')
MINT, AMBER = '22313F', '0B6E7A'
IX, IW, JX = 1.10, 16.07, 18.79
SRC_H = dict(abstract=8.3, intro=9.6, datameth=0, results=23.7, secure=9.4, concl=3.2, ack=0)
yL = 6.50; GAP = 0.45
pos = {}
pos['abstract'] = (LX, yL, BW, SRC_H['abstract']); yL += SRC_H['abstract'] + GAP
pos['intro'] = (LX, yL, BW, SRC_H['intro']); yL += SRC_H['intro'] + GAP
pos['datameth'] = (LX, yL, BW, 47.33 - yL)
yR = 6.50
for k in ('results', 'secure', 'concl'):
    pos[k] = (RX, yR, BW, SRC_H[k]); yR += SRC_H[k] + GAP
pos['ack'] = (RX, yR, BW, 47.33 - yR)
for k, v in pos.items(): place(k, *v)
for k in ('datameth', 'secure'): by_name[SEC[k][0]].fill.solid(); by_name[SEC[k][0]].fill.fore_color.rgb = rgb(RUST if k == 'datameth' else SLATE)
SUB = lambda t, z=28: dict(runs=[(t, {'bold': True, 'color': AMBER, 'size': z})], after=4, size=z)
TILE = '1F2D3A'
def block(x, y, w, paras, size=24):
    tb, h = add_text(x, y, w, paras, size=size); return y + h
def AMBN(t): return (t, {'bold': True, 'color': AMBER})
def ends(name, y): print(f'{name}: content ends {y:.2f}, box ends {pos[name][1] + pos[name][3]:.2f}', 'OVERFLOW' if y > pos[name][1] + pos[name][3] - 0.2 else '')

# ---------- ABSTRACT ----------
S = 28
y = block(IX, pos['abstract'][1] + 1.55, IW, [P('Smart lake monitoring depends on sensor buoys, but their readings can be missing, frozen, wrong or tampered with. We screened 330,384 readings (1.9 million sensor values) from four NOAA-GLERL buoys in western Lake Erie, 2015–2026, with simple, explainable tests, and compared them with the operators’ own quality flags. A local replay prototype, a PySpark port and a proposed secure cloud design complete the framework. All results use archived US data.', after=4)], size=S) + 0.12
y = block(IX, y, IW, [SUB('Key findings')]) + 0.05
tw = 3.9; tg = (IW - 4 * tw) / 3
for k, (big, small, col) in enumerate([('99%', 'of flagged temperature readings come from one flat-line rule', '17324D'), ('31 + 36 days', 'dead probe at WE2 and frozen sensor at WE8, found by simple rules', '1B8A9A'),
                                      ('81%', 'of +3 °C slow drifts caught by neighbour buoys; single-sensor tests caught 0%', '17324D'), ('Same flags', 'Spark = Pandas (4 of 42,069 differ) but slower: 49 s vs 0.7 s', '1B8A9A')]):
    x = IX + k * (tw + tg); card(x, y, tw, 2.75, fill=col, radius=0.06)
    add_text(x + 0.18, y + 0.12, tw - 0.36, [dict(runs=[(big, {'bold': True, 'color': 'FFFFFF', 'size': 38 if len(big) < 8 else 32})], size=38, after=3), P(small, size=22, color='EAF4F7', after=0)], size=22)
y += 2.75
ends('abstract', y)

# ---------- INTRODUCTION ----------
S = 28
y = pos['intro'][1] + 1.55
y = block(IX, y, IW, [SUB('Background')])
y = block(IX, y, IW, [
    B('Western Lake Erie has toxic algae blooms. In 2014 one forced the city of Toledo to issue a tap-water ban [1].'),
    B('NOAA GLERL buoys report water quality every 15 minutes in the open-water season [2].'),
    B('Sensors fail, freeze or can be tampered with, so decisions need data that can be trusted.'),
], size=S) + 0.1
y = block(IX, y, IW, [SUB('Problem and questions')])
y = block(IX, y, IW, [
    P('Can simple tests find faulty buoy readings, and can neighbouring buoys tell a natural bloom from a fault?', after=5),
    PB([AMBN('RQ1 '), ('What do the records cover, and how much is missing?', {})], after=2),
    PB([AMBN('RQ2 '), ('What are the operators’ quality flags made of?', {})], after=2),
    PB([AMBN('RQ3 '), ('Which faults do simple tests catch (real and synthetic)?', {})], after=2),
    PB([AMBN('RQ4 '), ('Do neighbouring buoys help with slow drift?', {})], after=2),
    PB([AMBN('RQ5 '), ('(Design only) How could a secure cloud pipeline protect the data?', {})], after=0),
], size=S)
ends('intro', y)

# ---------- DATA AND METHODS ----------
S = 29; y0 = pos['datameth'][1]
y = y0 + 1.55
y = block(IX, y, IW, [SUB('Data')])
y = block(IX, y, IW, [P('Four Western Erie buoys via GLOS Seagull; archived CSVs downloaded Oct 2026. Six sensors: chlorophyll, phycocyanin, oxygen, temperature, turbidity, conductivity.', after=4)], size=S) + 0.3
mh = picture('../../figures/t_map.png'.replace('../../figures/t_', ''), IX, y, 7.8, pad=0.06) if False else None
from PIL import Image
MAPF = '/home/claude/proj/figures/t_map.png'
im = Image.open(MAPF); mw = 7.8; mh = mw * im.height / im.width
card(IX, y, mw + 0.12, mh + 0.12); sp.add_picture(MAPF, inch(IX + 0.06), inch(y + 0.06), inch(mw), inch(mh)); mh += 0.12
th = table(IX + 8.15, y, [1.05, 1.5, 1.75, 1.55, 1.57], [
    ['Buoy', 'Dataset', 'Readings', 'Period', '15-min'],
    ['WE2', 'obs_80', '111,403', '2015–26', '96%'], ['WE4', 'obs_81', '82,094', '2015–26', '78%'],
    ['WE8', 'obs_82', '104,048', '2015–26', '99%'], ['WE13', 'obs_215', '32,839', '2016–19', '94%']], size=20, row_h=0.74)
y = y + max(mh, th) + 0.3
y = block(IX, y, IW, [P('No 2025 data; 11–15 gaps over 7 days per buoy (winter). −999 is the documented missing-value code.', size=22, color='22313F', after=2)], size=22) + 0.3
y = block(IX, y, IW, [SUB('Methods')]) + 0.05
for k, (nm, col) in enumerate([('1 Tidy', '17324D'), ('2 Read flags', '1F5A78'), ('3 Our tests', '1B8A9A'), ('4 Synthetic', '2C9DAB'), ('5 Spark check', '48B3BE')]):
    c = sp.add_shape(MSO_SHAPE.PENTAGON if k == 0 else MSO_SHAPE.CHEVRON, inch(IX + k * 3.17), inch(y), inch(3.35), inch(0.95))
    c.fill.solid(); c.fill.fore_color.rgb = rgb(col); c.line.fill.background(); shape_text(c, nm, 22, 'FFFFFF', True)
y += 1.15
y = block(IX, y, IW, [
    BB([AMBN('Tidy: '), ('SHA-256 of raw files; −999 → missing; K → °C; merge the two identical phycocyanin columns.', {})]),
    BB([AMBN('Operator flags: '), ('1 pass, 2 not evaluated, 3 suspect, 4 fail [3]; we test how they are made.', {})]),
    BB([AMBN('Our tests: '), ('dead probe (4 of 5 sensors read 0); spike (9-reading median, 6× robust scale [4]); stuck (24 identical readings, gaps up to 20 min); neighbour check (temperature vs median of other buoys, 6 h rolling median).', {})]),
    BB([AMBN('Synthetic tests: '), ('spikes, 6-hour stuck values and slow drifts added to a copy (99 or 36 events each).', {})]),
    BB([AMBN('Spark and Pandas: '), ('same rules in both, compared flag by flag; timed on one CPU core of a cloud sandbox (Xeon 2.1 GHz, 4 GB RAM, PySpark 4.3.0, Pandas 3.0.6). An earlier run on my laptop (Spark 3.5.6, older settings) was also slow: 563 s for the three detectors, start-up included.', {})]),
], size=S) + 0.3
y = block(IX, y, IW, [SUB('Limitations')])
y = block(IX, y, IW, [
    B('US lake data, not Indian; archived replay, not a live feed.'),
    B('Flags are automatic tests, not confirmed faults; our thresholds are analyst choices.'),
    B('Drift of 1–2 °C is mostly missed; the stuck test skips gaps over 20 min.'),
    B('Spark was timed on one core and a small data set; the cloud parts are a design, not built.'),
], size=S)
ends('datameth', y)

# ---------- RESULTS ----------
S = 24; y0 = pos['results'][1]; HX = JX + 8.15; HW = 7.92
def pic2(name, x, y, w): return picture(name, x, y, w, pad=0.06)
y = y0 + 1.55
y = block(JX, y, IW, [SUB('1  Operator flags are not a fault list')])
y = block(JX, y, IW, [P('Operators flag 43–47% of algae, oxygen and turbidity readings and 78% of temperature readings. One rule causes 99% of temperature flags. In 2016–2019, 17–20% of evaluated readings were flagged; in 2021–2026, 93–100%.', after=2)], size=S) + 0.08
h1 = pic2('tempflags.png', JX, y, 7.8); h2 = pic2('comp.png', HX, y, 7.8); y += max(h1, h2) + 0.15
y = block(JX, y, IW, [SUB('2  Real faults our tests find')])
y = block(JX, y, IW, [P('Autumn 2015: all WE2 sensors read 0 for 31 days (2,983 readings; operators flagged about 99%). WE8’s phycocyanin sensor stayed at 2.31 RFU for 36 days (3,458 readings).', after=2)], size=S) + 0.08
y += pic2('faults.png', JX, y, 15.8) + 0.15
yy = y
ya = block(JX, yy, HW, [SUB('3  Slow drift: neighbours help')])
ya = block(JX, ya, HW, [P('Synthetic faults on a copy: spikes caught 94–95%, 6-hour stuck values 65–73%. A +3 °C drift is caught late: median 5 days.', after=2)], size=S) + 0.08
ya += pic2('drift.png', JX, ya, 7.8)
yb = block(HX, yy, HW, [SUB('4  Bloom or fault?')])
yb = block(HX, yb, HW, [P('Of 13,521 high-chlorophyll readings, most sit in slow, shared rises (bloom-like). 239 short isolated spikes (290 readings) are the candidates for sensor faults, not confirmed.', after=2)], size=S) + 0.12
hb = pic2('bloom.png', HX, yb, 7.8)
y = max(ya, yb + hb) + 0.18
y = block(JX, y, IW, [SUB('5  Spark vs Pandas: same flags, slower here')])
y = block(JX, y, IW, [P('Same rules, same data, one CPU core (median of 3 runs; ×50 test: 1 run). Spark matched Pandas but was slower on every job. Synthetic = WE2 temperature copied 10× or 50×.', after=2)], size=S) + 0.08
ty = y
tab_h = table(JX, ty, [2.5, 1.7, 1.7, 1.9], [['Detector', 'Pandas', 'Spark', 'Overlap'], ['Dead probe', '3,071', '3,071', '100%'], ['Spike', '27,988', '27,984', '99.99%'],
                                            ['Stuck', '10,137', '10,137', '100%'], ['Neighbour', '873', '873', '100%']], size=20, row_h=0.55)
yy2 = block(JX, ty + tab_h + 0.12, HW, [P('The 4 differing spike rows come from CSV number parsing at the exact threshold. Shuffle partitions, Parquet and lag/lead windows did not speed Spark up.', after=0)], size=22)
t_h = pic2('timing.png', HX, ty, 7.8); y = max(yy2, ty + t_h) + 0.1
ends('results', y)

# ---------- CYBERSECURITY AND PIPELINE ----------
y0 = pos['secure'][1]; y = y0 + 1.55
y = block(JX, y, IW, [SUB('Local prototype and proposed cloud design')])
names = [('Buoy sensors', '5B6B7C'), ('Ingest + validate', TEAL), ('Store + hash', TEAL), ('Detect', TEAL), ('Alert + review', TEAL)]
bw, gap = 2.85, 0.455
for i, (nm, col) in enumerate(names):
    x = JX + i * (bw + gap)
    b = sp.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(x), inch(y), inch(bw), inch(1.05)); b.adjustments[0] = 0.12
    b.fill.solid(); b.fill.fore_color.rgb = rgb(col); b.line.fill.background(); shape_text(b, nm, 22)
    if i < 4:
        a = sp.add_shape(MSO_SHAPE.RIGHT_ARROW, inch(x + bw + 0.06), inch(y + 0.33), inch(gap - 0.12), inch(0.4)); a.fill.solid(); a.fill.fore_color.rgb = rgb(MINT); a.line.fill.background()
y += 1.2
st = sp.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(JX), inch(y), inch(IW), inch(1.05)); st.adjustments[0] = 0.1
st.fill.solid(); st.fill.fore_color.rgb = rgb('FDF0DA'); st.line.color.rgb = rgb('E89B2D'); st.line.width = Pt(2.5); st.line.dash_style = 4
shape_text(st, 'Designed, not built: device certificates and mutual TLS · object store with Object Lock · IAM · KMS encryption · audit logs', 22, DARK, False)
y += 1.2
y = block(JX, y, IW, [P('Teal = ran locally on archived data (replay, not live). WE2 2018 replay: 11,425 readings in 124 daily batches, median 22 ms each; 1,083 spike alerts, identical to the batch run.', size=22, color=MINT, after=0)], size=22) + 0.12
tt = table(JX, y, [4.2, 4.6, 7.27], [
    ['Threat to the data', 'Design control', 'Evidence from this project'],
    ['Dead, frozen or glitchy sensor', 'Range, stuck and spike checks', 'Tested: real cases found; spikes 94–95% caught (synthetic)'],
    ['Slow drift or manipulation', 'Cross-buoy checks; human review', 'Tested (synthetic): +3 °C drift 81% caught, +1 °C only 14%'],
    ['Silent edits to stored data', 'Immutable raw zone, signed manifests', 'Tested: SHA-256 caught a 1-character edit; chained log caught an edited entry'],
    ['Spoofing, eavesdropping, unauthorised access', 'Mutual TLS [5]; IAM and KMS [6]', 'Not built or tested'],
], size=20, row_fills=['E4F2F4', 'FDF0DA', 'E4F2F4', 'EEF1F5'])
y += tt + 0.1
ends('secure', y)

# ---------- CONCLUSION ----------
y = pos['concl'][1] + 1.5
y = block(JX, y, IW, [
    B('Operator flags are not a fault list: one rule drives most of them.', size=24),
    B('Simple, explainable tests find real faults; neighbour buoys catch drift of 3 °C or more.', size=24),
    B('Next: ask NOAA and GLOS why flags stop; test Spark on much larger data.', size=24),
], size=24)
ends('concl', y)

# ---------- ACKNOWLEDGEMENTS ----------
ay = pos['ack'][1]; ah = pos['ack'][3]
hd = by_name[SEC['ack'][1]]; hd.top = inch(ay + 0.2); bar_of['ack'].top = inch(ay + 0.92)
add_text(JX, ay + 1.05, 13.2, [
    P('Data: NOAA GLERL buoys, served by GLOS Seagull (glos.org/seagull); we thank NOAA GLERL and GLOS. Analysis, figures and design are the author’s. Code and results: github.com/Mannat29/lake-buoy-anomaly-detection', size=16, after=3),
    P('[1] Fondriest Environmental (2014) Toledo water crisis hastens Lake Erie buoy near water intake. [2] NOAA GLERL & CIGLR, Lake Erie HAB water-quality data, NOAA NCEI. [3] NOAA GLERL Tech. Memo. GLERL-181 (2026), buoy quality-control tests. [4] Hampel (1974) J. Am. Stat. Assoc. 69, 383–393. [5] NIST SP 800-52 Rev. 2. [6] AWS, Security best practices in IAM.', size=13, after=0)], size=16, color=MINT)
qs = min(2.1, ah - 1.15); qx = 32.2
card(qx - 0.1, ay + 0.25, qs + 0.2, qs + 0.75, fill=WHITE, line='C9D3DC')
add_text(qx - 0.05, ay + 0.28, qs + 0.1, [dict(runs=[('Scan here', {'bold': True, 'color': '0B6E7A', 'size': 18})], size=18, align=PP_ALIGN.CENTER)], size=18)
sp.add_picture('/home/claude/proj/figures/repo_qr.png', inch(qx), inch(ay + 0.8), inch(qs), inch(qs))
# ---------- light card restyle (page, boxes, headings) ----------
try:
    slide.background.fill.solid(); slide.background.fill.fore_color.rgb = rgb('DCE3EA')
except Exception as ex: print('bg', ex)
for k in pos:
    r = by_name[SEC[k][0]]; r.fill.solid(); r.fill.fore_color.rgb = rgb('F7F9FB'); r.line.color.rgb = rgb('C9D3DC'); r.line.width = Pt(1.5)
    for run in by_name[SEC[k][1]].text_frame.paragraphs[0].runs: run.font.color.rgb = rgb('17324D')
    bar_of[k].fill.solid(); bar_of[k].fill.fore_color.rgb = rgb('1B8A9A')
prs.save(OUT); print('saved')
