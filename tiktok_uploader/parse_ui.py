import sys, re, pathlib

xml = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")

# Find buttons and text fields
for m in re.finditer(
    r'<node\s+([^>]*?)>',
    xml
):
    attrs = m.group(1)
    text_m = re.search(r'text="([^"]*)"', attrs)
    desc_m = re.search(r'content-desc="([^"]*)"', attrs)
    cls_m = re.search(r'class="([^"]*)"', attrs)
    bounds_m = re.search(r'bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"', attrs)
    clickable_m = re.search(r'clickable="([^"]*)"', attrs)
    
    text = text_m.group(1) if text_m else ""
    desc = desc_m.group(1) if desc_m else ""
    cls = cls_m.group(1) if cls_m else ""
    bounds = f"[{bounds_m.group(1)},{bounds_m.group(2)}]-[{bounds_m.group(3)},{bounds_m.group(4)}]" if bounds_m else ""
    clickable = clickable_m.group(1) if clickable_m else ""
    
    label = text or desc
    if label.strip():
        print(f"  {bounds} '{label}' clickable={clickable} class={cls}")
