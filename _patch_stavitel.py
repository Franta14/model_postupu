NEW_BODY = '''    def spocitat_trasy(self):
        self.hotovo = True
        self.ax.set_title("POCITAM TRASY...", color="red", fontweight="bold")
        self.fig.canvas.draw()
        self.fig.canvas.flush_events()

        working_grid_base = cost_grid_base.copy()
        colors = ["#DD0000", "#00AA00", "#0055DD"]

        bod_A, bod_B = self.body[0], self.body[1]
        print(f"\\nResim postup: Start -> Cil")
        s_y, s_x = img_to_grid(bod_A[0], bod_A[1])
        g_y, g_x = img_to_grid(bod_B[0], bod_B[1])

        prima_vzdalenost_m = math.hypot(g_x - s_x, g_y - s_y) * grid_size * NASOBIC_MERITKA
        rng = np.random.default_rng(seed=42)

        # ================================================================
        # POMOCNE FUNKCE
        # ================================================================
        def spocitat_metriky(cesta):
            vzd = prev = usili = 0.0
            for j in range(1, len(cesta)):
                p1, p2 = cesta[j-1], cesta[j]
                dg = math.hypot(p2[1]-p1[1], p2[0]-p1[0]) * grid_size
                vzd += dg * NASOBIC_MERITKA
                z1 = elev_grid[int(p1[0]), int(p1[1])]
                z2 = elev_grid[int(p2[0]), int(p2[1])]
                if z2 > z1: prev += (z2 - z1)
                sk = (z2-z1) / (dg * NASOBIC_MERITKA) if dg > 0 else 0
                if sk > 0:   hm = 1.0 + sk * 0.5
                elif sk < 0: hm = (1.0 + sk*0.4) if sk >= -0.40 else (1.0 - 0.28 + (abs(sk)-0.40)*1.1)
                else:        hm = 1.0
                usili += dg * working_grid_base[int(p2[0]), int(p2[1])] * hm
            return vzd, prev, usili

        def merit_podobnost(cesta_nova, prijate_cesty):
            if not prijate_cesty:
                return 0.0
            maska = np.zeros((height, width), dtype=bool)
            r = PODOBNOST_RADIUS
            for co in prijate_cesty:
                for (py, px) in co[::4]:
                    y, x = int(py), int(px)
                    maska[max(0,y-r):min(height,y+r+1),
                          max(0,x-r):min(width, x+r+1)] = True
            sdil = sum(1 for (py, px) in cesta_nova if maska[int(py), int(px)])
            return sdil / max(1, len(cesta_nova))

        def vytvor_koridorovou_penalizaci(cesty, sila, sigma_px):
            """Vytvori siroky plynuly penalizacni kopec kolem vsech zadanych tras.
            
            Nakresli binarni stopu -> 3x separabilni prumerovani (= priblizeni Gaussu)
            -> vysledek je hladky kopec s maximem na trase.
            """
            stopa = np.zeros((height, width), dtype=np.float32)
            for cesta in cesty:
                for (py, px) in cesta[::2]:
                    y, x = int(py), int(px)
                    if 0 <= y < height and 0 <= x < width:
                        stopa[y, x] = 1.0
            
            # 3x separabilni prumerovani (kazdy pruchod sirsi okno)
            # To vytvori hladky Gaussovity kopec
            kopec = stopa.copy()
            for pruchod in range(3):
                r = sigma_px // 3 + pruchod * (sigma_px // 4)
                r = max(1, r)
                kernel = np.ones(2*r+1, dtype=np.float32) / (2*r+1)
                # Horizontalni prumer
                for row in range(height):
                    kopec[row, :] = np.convolve(kopec[row, :], kernel, mode='same')
                # Vertikalni prumer
                for col in range(width):
                    kopec[:, col] = np.convolve(kopec[:, col], kernel, mode='same')
            
            # Normalizace na [0, 1]
            mx = kopec.max()
            if mx > 1e-8:
                kopec = kopec / mx
            
            # Penalty mapa: 1.0 (zadna penalizace) az 'sila' (na strede trasy)
            return 1.0 + kopec * (sila - 1.0)

        # ================================================================
        # HLAVNI SMYCKA: Iterativni Gaussovsky koridor
        #
        # 1. Varianta 1: Cisty A* (+ jemny sum)
        # 2. Varianta 2: A* na gridu s ~100m sirokym penalizacnim kopcem
        #    kolem var.1 -> MUSI hledat jiny strategicky koridor
        # 3. Varianta 3: Penalizace kolem var.1 + var.2
        #
        # Celkem: 3 behy A* (= rychle!)
        # ================================================================
        
        KORIDOR_SIGMA_PX = 20   # ~100m sirka koridoru
        KORIDOR_SILA     = 2.0  # +100% na stred trasy
        
        prijate_cesty = []
        vybrane = []

        for var_i in range(POCET_VARIANT):
            print(f"   Hledam variantu {var_i+1}...", flush=True)
            
            # Sestavime grid: zaklad + koridorova penalizace + jemny sum
            if prijate_cesty:
                print(f"      Pocitam penalizacni koridor ({len(prijate_cesty)} tras)...", flush=True)
                penalty_mapa = vytvor_koridorovou_penalizaci(
                    prijate_cesty, KORIDOR_SILA, KORIDOR_SIGMA_PX)
                wg = np.where(working_grid_base < 9000.0,
                              working_grid_base * penalty_mapa,
                              working_grid_base)
            else:
                wg = working_grid_base.copy()
            
            # Jemny sum pro prirozene zakriveni
            noise = rng.uniform(0.990, 1.010, wg.shape).astype(np.float32)
            wg = np.where(wg < 9000.0, wg * noise, wg)
            
            cesta = astar(wg, (s_y, s_x), (g_y, g_x))
            if cesta is None:
                print(f"      Varianta {var_i+1}: A* nenaslo cestu.")
                continue
            
            # Metriky na ORIGINALNIM gridu
            vzd, prev, usili = spocitat_metriky(cesta)
            vzd_km = vzd / 1000.0
            
            # Kontrola max. delky
            if vzd > prima_vzdalenost_m * MAX_DETOUR_KOEF:
                print(f"      Varianta {var_i+1}: prilis dlouha ({vzd_km:.2f}km > limit {prima_vzdalenost_m*MAX_DETOUR_KOEF/1000:.2f}km)")
                # I tak ji pridame do penalizace, aby dalsi varianta hledala jeste jinde
                prijate_cesty.append(cesta)
                continue
            
            sim = merit_podobnost(cesta, prijate_cesty)
            print(f"      Nalezena: {vzd_km:.2f}km, podobnost={sim*100:.0f}%")
            
            prijate_cesty.append(cesta)
            vybrane.append((usili, vzd, prev, cesta))

        # ================================================================
        # VYKRESLENI
        # ================================================================
        nalezeno = 0
        for usili, vzd, prev, cesta in vybrane:
            vzd_km = vzd / 1000.0
            cas_min = usili * NASOBIC_MERITKA * (zakladni_tempo_desetinne / (1000.0 * CENA_LESNI_CESTY))
            cas_c = int(cas_min); cas_v = int((cas_min - cas_c) * 60)
            t_m   = int(cas_min / vzd_km) if vzd_km > 0 else 0
            t_v   = int(((cas_min / vzd_km) - t_m) * 60) if vzd_km > 0 else 0

            nalezeno += 1
            print(f"   Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d} ({t_m}:{t_v:02d}/km)")
            label = f"Var {nalezeno}: {vzd_km:.2f} km | +{prev:.0f}m | {cas_c}:{cas_v:02d}"

            cesta_viz = vyhlad_cestu(cesta, working_grid_base, vyhlazeni=VYHLAZENI_BUNEK) if ZAPNOUT_VYHLAZENI else cesta
            cesta_viz = prirozeny_jitter(cesta_viz, rng, working_grid_base, amplituda=3.5, delka_korelace=20)

            wx, wy = [], []
            for py, px in cesta_viz:
                u, v = grid_to_img(py, px)
                wx.append(u); wy.append(v)
            if len(wx) > 1:
                wx[0], wy[0] = bod_A[0], bod_A[1]
                wx[-1], wy[-1] = bod_B[0], bod_B[1]

            barva = colors[(nalezeno-1) % len(colors)]
            l1, = self.ax.plot(wx, wy, color=barva, linewidth=4, alpha=0.9, label=label)
            l2, = self.ax.plot(wx, wy, color="white", linewidth=1, alpha=0.8)
            self.vykreslene_trasy.extend([l1, l2])

        if nalezeno:
            self.ax.legend(loc="upper left", title="Postupy a Casy", fontsize=10,
                           title_fontsize=12, facecolor="white", framealpha=0.9, edgecolor="black")
            self.ax.set_title("HOTOVO!" + self.navod_hotovo, color="green", fontweight="bold")
            print(f"\\nHotovo! Vykresleno {nalezeno}/{POCET_VARIANT} variant.")
        else:
            self.ax.set_title("NENALEZENO!" + self.navod_hotovo, color="red", fontweight="bold")
            print("\\nNenasla se zadna varianta.")

        self.fig.canvas.draw_idle()
'''
