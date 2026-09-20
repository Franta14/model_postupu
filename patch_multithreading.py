import re

with open('9_generator_postupu.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Najdeme telo cyklu (od for idx... az po elapsed_phase2 = time.time() - t_start)
pattern = r'(for idx, \(p1, p2, dist_m\) in enumerate\(candidates\):.*?)(elapsed_phase2 = time\.time\(\) - t_start)'
match = re.search(pattern, text, re.DOTALL)
if not match:
    print('Error: nenasel for cyklus')
    exit(1)

body_raw = match.group(1)

new_code = """
import concurrent.futures

def _eval_candidate(args):
    idx, p1, p2, dist_m = args
"""

lines = body_raw.split('\n')
for line in lines[1:]: # preskocime radek s 'for idx...'
    if 'if idx % 25 == 0:' in line:
        continue # progress budeme resit jinak
    if 'elapsed = time.time() - t_start' in line: continue
    if 'eta = ' in line: continue
    if 'print(f"   [{idx' in line: continue
    if 'else:' in line: continue
    
    if 'skipped_boring += 1' in line:
        continue
    
    line = line.replace('continue', 'return None')
    line = line.replace('break', 'return None')
    if 'scored_postupy.append({' in line:
        new_code += line.replace('scored_postupy.append({', 'return {') + '\n'
        continue
    if '    })' in line:
        new_code += '    }\n'
        continue
        
    new_code += line + '\n'

new_code += """
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    futures = [ex.submit(_eval_candidate, (i, p1, p2, d)) for i, (p1, p2, d) in enumerate(candidates)]
    
    for i, future in enumerate(concurrent.futures.as_completed(futures)):
        if i % 25 == 0:
            elapsed = time.time() - t_start
            if i > 0:
                eta = (elapsed / i) * (len(candidates) - i)
                print(f"   [{i:>3}/{len(candidates)}] {len(scored_postupy)} zajimavych | ~{eta:.0f}s zbyva", flush=True)
            else:
                print(f"   [{i:>3}/{len(candidates)}] Startuji...", flush=True)
                
        res = future.result()
        if res is not None:
            scored_postupy.append(res)
        else:
            skipped_boring += 1

"""

text = text[:match.start()] + new_code + text[match.end(1):]

with open('9_generator_postupu.py', 'w', encoding='utf-8') as f:
    f.write(text)
print("Patch aplikovan!")
