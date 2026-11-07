"""Fill the LAKE 2026 36x48 in template (perceptualpewter_36x48.pptx) with the buoy-data poster."""
import copy, math, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from lxml import etree

SRC = '/mnt/user-data/uploads/perceptualpewter_36x48.pptx'
OUT = '/home/claude/lake-buoy-research/poster/lake2026_poster_v3.pptx'
FIG = '/home/claude/lake-buoy-research/figures/t_'
prs = Presentation(SRC)
slide = prs.slides[0]
sp = slide.shapes
by_name = {s.name: s for s in sp}
MINT, AMBER, WHITE, DARK, TEAL, SLATE, RUST, LTEAL, LGREY = 'F0FAF5', 'F6C85F', 'FFFFFF', '1C2733', '1B8A9A', '2E4053', 'A93226', 'E4F2F4', 'EEF1F5'
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
set_runs(auth_box, [('Mannat Tomar¹, Research Guide: [add name]²', 28, True, 'FFFFFF'),
                    ('¹BCA (Hons.) Data Science, Minor in Cybersecurity, Chanakya University, Devanahalli, Bengaluru | ²[add guide’s department / institution]', 19, False, 'D7E6F5'),
                    ('mannatt.bca23@chanakyauniversity.edu.in | Bengaluru, Karnataka | December 17-20, 2026 | www.lake2026conference.in', 17, False, 'C8DCEB'),
                    ('Theme: IoT Buoys, Real-time Sensor Networks & Hydrological Monitoring', 17, False, 'C8DCEB')])

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
IX, IW = 1.10, 16.07          # inner text x / width (left)
JX = 18.79                    # inner text x (right)
place('abstract', LX, 6.50, BW, 9.10)
place('intro', LX, 16.20, BW, 10.40)
place('datameth', LX, 27.20, BW, 20.13)
place('results', RX, 6.50, BW, 19.40)
place('secure', RX, 26.50, BW, 10.40)
place('concl', RX, 37.50, BW, 5.70)
place('ack', RX, 43.80, BW, 3.53)
for k in ('datameth', 'secure'): by_name[SEC[k][0]].fill.solid(); by_name[SEC[k][0]].fill.fore_color.rgb = rgb(RUST if k == 'datameth' else SLATE)

SUB = lambda t, z=30: dict(runs=[(t, {'bold': True, 'color': AMBER, 'size': z})], after=4, size=z)


def block(x, y, w, paras, size=22):
    tb, h = add_text(x, y, w, paras, size=size); return y + h


# ---------- ABSTRACT ----------
y = 8.05
y = block(IX, y, IW, [P('Smart lake monitoring relies on sensor buoys, but their readings can be missing, frozen, wrong or tampered with. We screened 330,384 readings (about 1.9 million sensor values) from four NOAA-GLERL buoys in western Lake Erie, 2015–2026, with simple, explainable tests, and compared them with the operators’ own quality flags. A local replay prototype and a proposed secure cloud design complete the framework.', after=8)], size=28) + 0.15
y = block(IX, y, IW, [SUB('Key findings')], size=30)
y = block(IX, y, IW, [
    BB([('99% ', {'bold': True, 'color': AMBER}), ('of flagged temperature readings come from one flat-line rule; in 2021–2026, 93–100% of temperature readings are flagged.', {})]),
    BB([('Dead probe ', {'bold': True, 'color': AMBER}), ('at WE2 (31 days, all sensors read 0) and a frozen phycocyanin sensor at WE8 (36 days) found by simple rules.', {})]),
    BB([('81% ', {'bold': True, 'color': AMBER}), ('of +3 °C slow drifts caught by comparing neighbouring buoys; single-sensor tests caught 0%.', {})]),
], size=28)

# ---------- INTRODUCTION ----------
y = 16.20 + 1.55
y = block(IX, y, IW, [SUB('Background')])
y = block(IX, y, IW, [
    B('Western Lake Erie has toxic algae blooms. In 2014 one forced the city of Toledo to issue a tap-water ban [1].'),
    B('NOAA GLERL buoys report water quality every 15 minutes in the open-water season [2].'),
    B('Sensors fail, freeze or can be tampered with, so decisions need data that can be trusted.'),
], size=27) + 0.1
y = block(IX, y, IW, [SUB('Problem and questions')])
y = block(IX, y, IW, [
    P('Can simple tests find faulty buoy readings, and can neighbouring buoys and several sensors tell a natural bloom from a fault?', after=5),
    PB([('RQ1 ', {'bold': True, 'color': AMBER}), ('What do the records cover, and how much is missing?', {})], after=2),
    PB([('RQ2 ', {'bold': True, 'color': AMBER}), ('What are the operators’ quality flags made of?', {})], after=2),
    PB([('RQ3 ', {'bold': True, 'color': AMBER}), ('Which faults do simple tests catch (real and synthetic)?', {})], after=2),
    PB([('RQ4 ', {'bold': True, 'color': AMBER}), ('Do neighbouring buoys help with slow drift?', {})], after=2),
    PB([('RQ5 ', {'bold': True, 'color': AMBER}), ('(Design) How could a secure cloud pipeline protect the data?', {})], after=0),
], size=26)
print('intro ends', round(y, 2), 'box ends', 16.20 + 10.40)

# ---------- DATA AND METHODS ----------
y = 27.20 + 1.55
y = block(IX, y, IW, [SUB('Data')])
y = block(IX, y, IW, [P('Four Western Erie nutrient buoys, served by GLOS Seagull; archived CSVs downloaded Oct 2026. Six sensors: chlorophyll, phycocyanin, oxygen, temperature, turbidity, conductivity.', after=4)], size=27) + 0.12
mh = picture('map.png', IX, y, 7.9 - 0.28, pad=0.14)
th = table(IX + 8.15, y, [1.2, 1.5, 1.6, 1.75, 1.55], [
    ['Buoy', 'Dataset', 'Readings', 'Period', '15-min'],
    ['WE2', 'obs_80', '111,403', '2015–26', '96%'], ['WE4', 'obs_81', '82,094', '2015–26', '78%'],
    ['WE8', 'obs_82', '104,048', '2015–26', '99%'], ['WE13', 'obs_215', '32,839', '2016–19', '94%']], size=19)
y = y + max(mh, th) + 0.15
y = block(IX, y, IW, [P('No 2025 data; 11–15 gaps over 7 days per buoy (winter). −999 is the documented missing-value code.', size=19, color='F0FAF5', after=4)], size=19) + 0.1
y = block(IX, y, IW, [SUB('Methods')])
y = block(IX, y, IW, [
    BB([('Verify and tidy: ', {'bold': True, 'color': AMBER}), ('SHA-256 of raw files; −999 → missing; K → °C; merge two identical phycocyanin columns (r = 1.00).', {})], size=27),
    BB([('Read the flags: ', {'bold': True, 'color': AMBER}), ('1 pass, 2 not evaluated, 3 suspect, 4 fail [3]; test how they are made.', {})], size=27),
    BB([('Our tests: ', {'bold': True, 'color': AMBER}), ('dead probe, spike (9-reading median, 6× robust scale [4]), stuck (24 identical readings), neighbour check.', {})], size=27),
    BB([('Check: ', {'bold': True, 'color': AMBER}), ('labelled synthetic faults on a copy; bloom-vs-fault rules; replay prototype; timing.', {})], size=27),
], size=27) + 0.1
y = block(IX, y, IW, [SUB('Limitations')])
y = block(IX, y, IW, [
    B('US lake data, not Indian; archived replay, not a live feed.', size=27),
    B('Flags are automatic tests, not confirmed faults; mostly “not evaluated” after 2019 except temperature.', size=27),
    B('Thresholds are analyst choices; drift of 1–2 °C is mostly missed; the stuck test skips readings over 20 min apart.', size=27),
    B('Run in Pandas on one core (PySpark port not run here). Cloud parts are a design.', size=27),
], size=27)
print('datameth ends', round(y, 2), 'box ends', 27.20 + 20.13)

# ---------- RESULTS ----------
y = 6.50 + 1.55
y = block(JX, y, IW, [SUB('1  Operator flags are not a fault list', 27)])
y = block(JX, y, IW, [P('Flags exist for 43–47% of algae, oxygen and turbidity readings and 78% of temperature readings. One rule alone causes 99% of flagged temperature readings (flat-line), 43% of oxygen flags (above 110% saturation) and 27% of turbidity flags (below 2 NTU).', size=22, after=4)], size=22) + 0.08
y += picture('tempflags.png', JX, y, 15.8) + 0.18
y = block(JX, y, IW, [SUB('2  Real faults our tests find', 27)])
y = block(JX, y, IW, [P('Autumn 2015: all WE2 sensors read zero for 31 days (2,983 readings; operators flagged about 99%), and WE8’s phycocyanin sensor stayed at 2.31 RFU for 36 days.', size=22, after=4)], size=22) + 0.08
y += picture('faults.png', JX, y, 15.8) + 0.18
y = block(JX, y, IW, [SUB('3  Slow drift: neighbours help', 27)])
y = block(JX, y, IW, [P('Labelled synthetic faults on a copy: spikes caught 94–95%, 6-hour stuck values 65–73%. A +3 °C drift is caught after about 5 days.', size=22, after=4)], size=22) + 0.08
y += picture('drift.png', JX, y, 15.8) + 0.18
y = block(JX, y, IW, [SUB('4  Bloom or fault?', 27)])
y = block(JX, y, IW, [P('Of 13,521 high-chlorophyll readings, 81% sit in 67 sustained bloom-like events (seen at another buoy or with phycocyanin). 239 short isolated spikes remain (290 readings); operators flagged 84% of those vs 56% of bloom-like readings (flagged years only).', size=22, after=0)], size=22)
print('results ends', round(y, 2), 'box ends', 6.50 + 19.40)

# ---------- CYBERSECURITY AND PIPELINE ----------
y = 26.50 + 1.55
y = block(JX, y, IW, [SUB('Local prototype and proposed cloud design', 27)])
names = [('Buoy sensors', '5B6B7C'), ('Ingest + validate', TEAL), ('Store + hash', TEAL), ('Detect', TEAL), ('Alert + review', TEAL)]
bw, gap = 2.85, 0.455
for i, (nm, col) in enumerate(names):
    x = JX + i * (bw + gap)
    b = sp.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(x), inch(y), inch(bw), inch(1.25)); b.adjustments[0] = 0.12
    b.fill.solid(); b.fill.fore_color.rgb = rgb(col); b.line.fill.background(); shape_text(b, nm, 19)
    if i < 4:
        a = sp.add_shape(MSO_SHAPE.RIGHT_ARROW, inch(x + bw + 0.06), inch(y + 0.42), inch(gap - 0.12), inch(0.4)); a.fill.solid(); a.fill.fore_color.rgb = rgb(MINT); a.line.fill.background()
y += 1.4
st = sp.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, inch(JX), inch(y), inch(IW), inch(0.95)); st.adjustments[0] = 0.1
st.fill.solid(); st.fill.fore_color.rgb = rgb('FDF0DA'); st.line.color.rgb = rgb('E89B2D'); st.line.width = Pt(2.5); st.line.dash_style = 4
shape_text(st, 'Designed, not built: device certificates and mutual TLS · object store with Object Lock · IAM · KMS encryption · audit logs', 19, DARK, False)
y += 1.1
y = block(JX, y, IW, [P('Teal = ran locally on archived data (replay, not live). Replay of WE2 2018: 11,425 readings in 124 daily batches, median 22 ms each; 1,083 spike alerts identical to the batch run. All four buoys on one core in Pandas: about 5 s.', size=19, after=0)], size=19) + 0.15
tt = table(JX, y, [4.6, 5.0, 6.47], [
    ['Threat to the data', 'Design control', 'Evidence from this project'],
    ['Dead, frozen or glitchy sensor', 'Range, stuck and spike checks', 'Tested: real cases found; spikes 94–95% caught (synthetic)'],
    ['Slow drift or manipulation', 'Cross-buoy checks; human review', 'Tested (synthetic): +3 °C drift 81%, +1 °C only 14%'],
    ['Silent edits to stored data', 'Immutable raw zone, signed manifests', 'Tested: SHA-256 caught a 1-character edit; chained log caught an edited entry'],
    ['Spoofing, eavesdropping, unauthorised access', 'Mutual TLS [5]; IAM and KMS [6]', 'Not built or tested'],
], size=18, row_fills=['E4F2F4', 'FDF0DA', 'E4F2F4', 'EEF1F5'])
y += tt + 0.12
print('secure ends', round(y, 2), 'box ends', 26.50 + 10.40)

# ---------- CONCLUSION ----------
y = 37.50 + 1.55
y = block(JX, y, IW, [
    B('Operator flags are not a fault list: one rule drives most of them, and 93–100% of temperature readings are flagged after 2021.', size=25),
    B('Simple, explainable tests find real faults, and neighbouring buoys catch drift of 3 °C or more.', size=25),
    B('Next: ask NOAA and GLOS why flags stop, confirm candidates with operators, add Indian lake data when open sensor data exist, port to PySpark and a cloud sandbox.', size=25),
], size=25)
print('concl ends', round(y, 2), 'box ends', 37.50 + 5.70)

# ---------- ACKNOWLEDGEMENTS ----------
y = 43.80 + 1.5
add_text(JX, y, 13.4, [
    P('Data: NOAA GLERL buoys, served by the Great Lakes Observing System (GLOS Seagull, glos.org/seagull). Analysis, figures and design are the author’s.', size=16, after=3),
    P('[1] Fondriest Environmental (2014) Toledo water crisis hastens Lake Erie buoy near water intake. [2] NOAA GLERL & CIGLR, Lake Erie HAB water-quality data, NOAA NCEI. [3] NOAA GLERL Tech. Memo. GLERL-181 (2026), buoy quality-control tests. [4] Hampel (1974) J. Am. Stat. Assoc. 69, 383–393. [5] NIST SP 800-52 Rev. 2. [6] AWS, Security best practices in IAM.', size=13.5, after=0)], size=13.5)
q = sp.add_shape(MSO_SHAPE.RECTANGLE, inch(32.4), inch(43.95), inch(2.5), inch(2.5)); q.fill.background(); q.line.color.rgb = rgb(MINT); q.line.width = Pt(2); q.line.dash_style = 4
shape_text(q, 'QR: add link to code and summary', 13, MINT, False)

prs.save(OUT); print('saved')
