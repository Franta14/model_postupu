import re

file_path = 'c:\\Users\\frant\\model_postupu\\6_finalni_stavitel.py'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace maska creation to 0.6
content = re.sub(
    r'maska = generator_engine\.vytvor_masku_elipsy\(\s*start, goal, height, width,\s*rozsireni=config\.ELIPSA_KOLMA_POLOOSA\s*\)',
    'maska = generator_engine.vytvor_masku_elipsy(\n            start, goal, height, width,\n            rozsireni=0.6\n        )',
    content
)

# Also update spocitat_vlastni_trasu maska
content = re.sub(
    r'maska_seg = generator_engine\.vytvor_masku_elipsy\(\s*seg_start, seg_goal, height, width, rozsireni=0\.50\s*\)',
    'maska_seg = generator_engine.vytvor_masku_elipsy(seg_start, seg_goal, height, width, rozsireni=0.6)',
    content
)

part1 = content.split('        vybrane = []')[0]
part2 = content.split('        print(f"   Celkem nalezeno {len(vybrane)} variant | {time.time()-t0:.2f}s", flush=True)')[1]

new_loop = '''        vybrane = []
        prijate_cesty = []
        working_grid = cost_grid_base.copy()
        
        for pokus in range(3):
            t_iter = time.time()
            dist_forward, parents_y_f, parents_x_f = generator_engine.dijkstra_heatmap(
                working_grid, elev_grid, start, maska, grid_size, NASOBIC_MERITKA, kopce_vaha=val_kopce,
                direction='forward'
            )
            
            if np.isinf(dist_forward[g_y, g_x]):
                if len(vybrane) == 0:
                    print("   CHYBA: Cil neni dosazitelny ze Startu!")
                    self.ax.set_title("NENALEZENO!" + self.navod_hotovo, color="red", fontweight="bold")
                    self.fig.canvas.draw_idle()
                    return
                else:
                    break
                    
            trasa = generator_engine.trasuj_cestu(parents_y_f, parents_x_f, start, goal)
            if not trasa:
                break
                
            trasa_vyhlazena = generator_engine.vyhlad_cestu(trasa, cost_grid_base, vyhlazeni=3)
            
            shoda = generator_engine.merit_podobnost(trasa_vyhlazena, prijate_cesty, height, width, PODOBNOST_RADIUS)
            if pokus > 0 and shoda > 0.8:
                print(f"      [Pokus {pokus+1} zahozen] prilis podobna (shoda {shoda*100:.0f}%)")
                continue
                
            prijate_cesty.append(trasa_vyhlazena)
            
            vzd, prev, usili, usili_real, road_ratio = self.spocitat_metriky(trasa_vyhlazena, cost_grid_base)
            vybrane.append((usili_real, vzd, prev, trasa_vyhlazena))
            
            print(f"      ✅ Var {len(vybrane)} (pokus {pokus+1}): {vzd/1000:.2f} km | +{prev:.0f}m | road={road_ratio*100:.0f}% | cas_vypoctu: {time.time()-t_iter:.2f}s", flush=True)
            
            working_grid = generator_engine.penalizuj_grid(working_grid, trasa_vyhlazena, PODOBNOST_RADIUS * 2)

'''

content_new = part1 + new_loop + '        print(f"   Celkem nalezeno {len(vybrane)} variant | {time.time()-t0:.2f}s", flush=True)' + part2

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content_new)

print('Replacement done')
