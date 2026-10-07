import pygame, random, time, os, math, json
import numpy as np

pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
pygame.init()

# ===== CONFIGURARE RAPIDA   =====

W, H        = 800, 600          # dimensiune fereastra
PANEL_H     = 130               # inaltime panou jos (scor/timp)
GAME_H      = H - PANEL_H       # inaltimea zonei de joc

SPEED_MULT  = 1.0               # <<< VITEZA tinte (creste -> mai rapid)
SPAWN_MULT  = 1.0               # <<< frecventa aparitie (<1 -> mai dese)
MULTI_CHANCE   = 0.25           # sansa ca o tinta sa fie multipla (2-5)
BOMB_CHANCE    = 1/10           # sansa de bomba
POWERUP_CHANCE = 1/12           # sansa de powerup
POWERUP_INTERVAL = 8.0          # secunde minime intre powerup-uri

R1, RN      = 26, 19            # raza tinta simpla / multipla
BOMB_R      = 23
POWERUP_R   = 23
BOMB_PENALTY = 10               # puncte pierdute cand lovesti bomba

FRENZY_COMBO_TRIGGER = 15       # combo necesar pentru Frenzy
FRENZY_DURATION      = 10.0     # durata modului Frenzy

SR = 44100                      # frecventa de esantionare audio

# Nivele: viteza de baza | timp intre spawn-uri | viata tinta |
#         scor pentru a trece nivelul | limita de timp (secunde)
LEVELS = [
    {"speed": 80,  "spawn_time": 2.0, "target_time": 4.0, "score_to_pass": 15,  "time_limit": 30},
    {"speed": 110, "spawn_time": 1.5, "target_time": 3.5, "score_to_pass": 30,  "time_limit": 35},
    {"speed": 140, "spawn_time": 1.2, "target_time": 3.0, "score_to_pass": 50,  "time_limit": 40},
    {"speed": 180, "spawn_time": 0.9, "target_time": 2.5, "score_to_pass": 80,  "time_limit": 45},
    {"speed": 240, "spawn_time": 0.6, "target_time": 1.8, "score_to_pass": 999, "time_limit": 50},
]

SCOREFILE, UNLOCK_FILE, STATS_FILE = "scores.txt", "unlocks.txt", "stats.json"

WHITE, BLACK = (255, 255, 255), (0, 0, 0)

screen = pygame.display.set_mode((W, H))
pygame.display.set_caption("Rapid Fire")

# Fonturi (Segoe UI cu fallback automat la fontul implicit)
def _f(size, bold=True): return pygame.font.SysFont("Segoe UI", size, bold=bold)
font_title = _f(48); font_big = _f(34); font_med = _f(22, False)
font_small = _f(16, False); font_combo = _f(30); font_tiny = _f(12, False)
font_huge = _f(80); font_grade = _f(100)

GRADE_THRESHOLDS = [(98,"SS"),(90,"S"),(75,"A"),(55,"B"),(35,"C"),(0,"D")]
GRADE_COLORS = {"SS":(255,215,0),"S":(255,160,0),"A":(80,220,80),
                "B":(80,160,255),"C":(200,200,60),"D":(180,80,80)}

POWERUP_TYPES = {
    "freeze": {"color":(100,210,255),"glow":(0,160,255),"label":"*","desc":"TIME FREEZE","duration":3.0},
    "slow":   {"color":(190,110,255),"glow":(130,0,255),"label":"S","desc":"SLOW MOTION","duration":5.0},
    "double": {"color":(255,225,0),  "glow":(255,170,0),"label":"x2","desc":"SCOR DUBLU","duration":6.0},
}

ACHIEVEMENTS = [
    {"id":"first_game",   "name":"Inceput bun",     "desc":"Termina primul joc",              "icon":"[!]"},
    {"id":"combo20",      "name":"Rapid Fire",       "desc":"Atinge combo x20",                "icon":"[F]"},
    {"id":"no_miss_lvl1", "name":"Ochire perfecta", "desc":"Treci lvl 1 fara nicio ratata",   "icon":"[O]"},
    {"id":"first_frenzy", "name":"Frenzy!",          "desc":"Activeaza modul Frenzy",          "icon":"[Z]"},
    {"id":"powerup_all",  "name":"Colectionar",      "desc":"Foloseste toate 3 power-up-uri",  "icon":"[*]"},
    {"id":"score_200",    "name":"200 de puncte",    "desc":"Obtine scor >= 200 intr-un joc",  "icon":"[2]"},
    {"id":"no_bomb",      "name":"Bomba? Ce bomba?", "desc":"Termina un joc fara a lua bomba", "icon":"[B]"},
    {"id":"legendar_skin","name":"Legendar",         "desc":"Debloca skinul Legendar",         "icon":"[L]"},
]

# ===== UTILITARE GRAFICE  =====

def safe_color3(c):
    # Garanteaza un tuplu RGB valid (0-255)
    try: return (max(0,min(255,int(c[0]))), max(0,min(255,int(c[1]))), max(0,min(255,int(c[2]))))
    except: return (255,255,255)

def draw_glow_circle(surf, color, center, radius, alpha=80, layers=6):
    # Halou luminos din mai multe cercuri transparente
    c = safe_color3(color); cx, cy = int(center[0]), int(center[1])
    for i in range(layers, 0, -1):
        r = radius + i*4
        gs = pygame.Surface((r*2+2, r*2+2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (*c, alpha//i), (r+1, r+1), r)
        surf.blit(gs, (cx-r-1, cy-r-1))

def draw_gradient_rect(surf, c1, c2, rect, vertical=True):
    # Dreptunghi cu gradient liniar intre doua culori
    x, y, w, h = rect; n = h if vertical else w
    for i in range(n):
        t = i/max(n,1); c = tuple(int(c1[j]+(c2[j]-c1[j])*t) for j in range(3))
        if vertical: pygame.draw.line(surf, c, (x,y+i), (x+w,y+i))
        else:        pygame.draw.line(surf, c, (x+i,y), (x+i,y+h))

def draw_rounded_rect_gradient(surf, c1, c2, rect, radius=10):
    # Gradient cu colturi rotunjite (masca aplicata rapid prin blend)
    x, y, w, h = rect
    tmp = pygame.Surface((w,h), pygame.SRCALPHA)
    draw_gradient_rect(tmp, c1, c2, (0,0,w,h))
    mask = pygame.Surface((w,h), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255,255,255,255), (0,0,w,h), border_radius=radius)
    tmp.blit(mask, (0,0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(tmp, (x,y))

def draw_glass_panel(surf, rect, color=(30,30,60), alpha=200, border_color=(100,100,180), radius=12):
    # Panou semi-transparent cu margine (efect "sticla")
    x, y, w, h = rect; c = safe_color3(color); bc = safe_color3(border_color)
    p = pygame.Surface((w,h), pygame.SRCALPHA)
    pygame.draw.rect(p, (*c, alpha), (0,0,w,h), border_radius=radius)
    surf.blit(p, (x,y))
    pygame.draw.rect(surf, bc, (x,y,w,h), 2, border_radius=radius)

def draw_progress_bar(surf, rect, ratio, color_fill, color_bg=(30,30,50), radius=6, glow=True):
    # Bara de progres (0..1). 'glow' adauga o dunga deschisa sus.
    x, y, w, h = rect; cf = safe_color3(color_fill)
    pygame.draw.rect(surf, color_bg, rect, border_radius=radius)
    fw = int(w*max(0.0, min(ratio,1.0)))
    if fw > 0:
        pygame.draw.rect(surf, cf, (x,y,fw,h), border_radius=radius)
        if glow:
            pygame.draw.rect(surf, tuple(min(255,v+45) for v in cf), (x,y,fw,max(1,h//2)), border_radius=radius)

# ===== BACKGROUND ANIMAT =====

_bg_particles = []
def _init_bg_particles(count=60):
    # Stelute care plutesc in fundal
    global _bg_particles
    _bg_particles = [{"x":random.uniform(0,W),"y":random.uniform(0,GAME_H),
        "vx":random.uniform(-8,8),"vy":random.uniform(-8,8),"size":random.uniform(0.8,2.2),
        "alpha":random.randint(30,100),"tw":random.uniform(0,6.28),"ts":random.uniform(1,3),
        "ci":random.randint(0,2)} for _ in range(count)]

def _update_bg_particles(dt, colors):
    for p in _bg_particles:
        p["x"]=(p["x"]+p["vx"]*dt)%W; p["y"]=(p["y"]+p["vy"]*dt)%GAME_H; p["tw"]+=p["ts"]*dt

def _draw_bg_particles(surf, colors):
    for p in _bg_particles:
        a = int(p["alpha"]*(0.5+0.5*math.sin(p["tw"]))); col = safe_color3(colors[p["ci"]%len(colors)])
        s = p["size"]; ps = pygame.Surface((int(s*2+2),int(s*2+2)), pygame.SRCALPHA)
        pygame.draw.circle(ps, (*col,a), (int(s+1),int(s+1)), int(s+0.5))
        surf.blit(ps, (int(p["x"]-s), int(p["y"]-s)))

_legend_stars = []
def _init_legend_stars():
    global _legend_stars
    _legend_stars = [{"x":random.uniform(0,W),"y":random.uniform(0,GAME_H),"vy":random.uniform(25,75),
        "size":random.uniform(1.2,3.5),"alpha":random.randint(60,200),
        "tw":random.uniform(0,6.28),"ts":random.uniform(1.5,4)} for _ in range(70)]

def _draw_legend_bg(surf, dt):
    # Fundal special pentru skinul LEGENDAR (ploaie de stele aurii)
    draw_gradient_rect(surf, (6,3,0), (12,7,0), (0,0,W,GAME_H))
    for r in range(200,0,-25):
        gs = pygame.Surface((r*2,r*2), pygame.SRCALPHA)
        pygame.draw.circle(gs, (255,140,0,int(20*(1-r/200))), (r,r), r)
        surf.blit(gs, (W//2-r, GAME_H//2-r))
    for s in _legend_stars:
        s["y"]+=s["vy"]*dt; s["tw"]+=s["ts"]*dt
        if s["y"] > GAME_H+5: s["y"]=-5; s["x"]=random.uniform(0,W)
        a = int(s["alpha"]*(0.4+0.6*abs(math.sin(s["tw"])))); sr = s["size"]
        ps = pygame.Surface((int(sr*2+2),int(sr*2+2)), pygame.SRCALPHA)
        pygame.draw.circle(ps, (255,int(190*(a/200)),0,a), (int(sr+1),int(sr+1)), int(sr+0.5))
        surf.blit(ps, (int(s["x"]-sr), int(s["y"]-sr)))

def draw_background(surf, skin, frenzy=False, dt=0):
    if skin.get("legendar"):
        _draw_legend_bg(surf, dt)
    else:
        draw_gradient_rect(surf, skin["bg_top"], skin["bg_bot"], (0,0,W,GAME_H))
        _update_bg_particles(dt, skin["particle_colors"]); _draw_bg_particles(surf, skin["particle_colors"])
        if skin.get("grid"):                      # grila optionala
            gc = tuple(c//6 for c in skin.get("grid_color",(200,200,200)))
            for x in range(0,W,50): pygame.draw.line(surf,gc,(x,0),(x,GAME_H),1)
            for y in range(0,GAME_H,50): pygame.draw.line(surf,gc,(0,y),(W,y),1)
        if skin.get("tricolor"):                  # benzi tricolore (skin Romania)
            for i,col in enumerate([(0,70,160),(255,210,0),(190,20,30)]):
                strip = pygame.Surface((10,GAME_H), pygame.SRCALPHA); strip.fill((*col,60))
                surf.blit(strip, (W-10*(3-i),0))
    if frenzy:                                     # rama pulsanta in Frenzy
        a = int(80+50*math.sin(time.time()*7))
        b = pygame.Surface((W,GAME_H), pygame.SRCALPHA)
        pygame.draw.rect(b, (255,100,0,a), (0,0,W,GAME_H), 5); surf.blit(b, (0,0))

def draw_panel(surf, skin, frenzy=False):
    draw_gradient_rect(surf, skin["panel_top"], skin["panel_bot"], (0,GAME_H,W,PANEL_H))
    pygame.draw.line(surf, skin["panel_line"], (0,GAME_H), (W,GAME_H), 2)
    if skin.get("tricolor"):
        for i,col in enumerate([(0,70,160),(255,210,0),(190,20,30)]):
            pygame.draw.rect(surf, col, (W//3*i, H-5, W//3, 5))
    if frenzy:
        fs = pygame.Surface((W,PANEL_H), pygame.SRCALPHA)
        fs.fill((255,80,0,int(120+80*math.sin(time.time()*5))//6)); surf.blit(fs, (0,GAME_H))
        pygame.draw.line(surf, (255,120,0), (0,GAME_H), (W,GAME_H), 2)

# ===== SUNETE  (generate procedural cu numpy) =====

def _to_stereo(mono):
    mono = np.clip(mono, -32767, 32767).astype(np.int16)
    return pygame.sndarray.make_sound(np.column_stack([mono, mono]))

def _tone(freq, dur, vol=0.5, decay=15):
    # O nota sinusoidala care se stinge
    t = np.linspace(0, dur, int(SR*dur), endpoint=False)
    return (np.sin(2*np.pi*freq*t)*32767*vol*np.exp(-t*decay)).astype(np.float32)

def _gap(d): return np.zeros(int(SR*d), dtype=np.float32)

def _arp(freqs, dur=0.1, g=0.02, vol=0.45, decay=13):
    # Arpegiu = mai multe note una dupa alta
    parts = []
    for f in freqs: parts += [_tone(f,dur,vol,decay), _gap(g)]
    return _to_stereo(np.concatenate(parts))

def init_sounds():
    try:
        th = np.linspace(0,0.12,int(SR*0.12),endpoint=False); fh = 880*np.exp(-th*15)
        hit = _to_stereo(np.sin(2*np.pi*fh*th)*32767*0.6*np.exp(-th*30))          # hit: sweep rapid
        tb = np.linspace(0,0.25,int(SR*0.25),endpoint=False)
        nb = np.random.uniform(-1,1,len(tb)).astype(np.float32); tn = np.sin(2*np.pi*80*tb).astype(np.float32)
        bomb = _to_stereo((nb*0.7+tn*0.3)*32767*0.8*np.exp(-tb*18))               # bomba: zgomot + bas
        return {"hit":hit, "miss":_to_stereo(_tone(140,0.18,0.5,18)), "bomb":bomb,
                "combo":_arp([660,990],0.11,0.04,0.55),
                "levelup":_arp([523,659,784],0.12,0.03,0.5,12),
                "gameover":_arp([440,370,311,261],0.15,0.03,0.5,10),
                "unlock":_arp([523,659,784,1046],0.10,0.02,0.5,10),
                "frenzy":_arp([300,400,500,700,900,1200],0.06,0.0,0.35,18),
                "powerup":_arp([440,660,880],0.08,0.0,0.4,14),
                "achievement":_arp([523,659,784,1046,1318],0.07,0.01,0.38,14)}
    except Exception as e:
        print(f"[Audio] {e}"); return None

def play_sfx(sounds, name):
    if sounds and name in sounds: sounds[name].play()

# ===== STATS / SCORURI / DEBLOCARI =====

def load_stats():
    d = {"total_games":0,"total_hits":0,"total_misses":0,"total_bombs_hit":0,"max_combo":0,
         "best_score":0,"unlocked_achievements":[],"powerups_used":[],"frenzy_count":0,"no_bomb_games":0}
    if not os.path.exists(STATS_FILE): return d
    try:
        with open(STATS_FILE) as f:
            data = json.load(f)
            for k,v in d.items(): data.setdefault(k,v)
            return data
    except: return d

def save_stats(s):
    with open(STATS_FILE,"w") as f: json.dump(s, f, indent=2)

def unlock_achievement(stats, aid):
    if aid not in stats["unlocked_achievements"]:
        stats["unlocked_achievements"].append(aid); save_stats(stats); return True
    return False

def load_unlocks():
    if not os.path.exists(UNLOCK_FILE): return set()
    with open(UNLOCK_FILE) as f: return set(l.strip() for l in f if l.strip())

def save_unlock(key):
    u = load_unlocks()
    if key not in u:
        u.add(key)
        with open(UNLOCK_FILE,"w") as f: f.write("\n".join(u)+"\n")

def is_skin_unlocked(key):
    return not SKINS.get(key,{}).get("locked", False) or key in load_unlocks()

def load_scores():
    if not os.path.exists(SCOREFILE): return []
    out = []
    with open(SCOREFILE) as f:
        for line in f:
            p = line.strip().split(",")
            if len(p)==2:
                try: out.append((p[0], int(p[1])))
                except: pass
    out.sort(key=lambda x:-x[1]); return out

def save_score(name, score):
    s = load_scores(); s.append((name,score)); s.sort(key=lambda x:-x[1])
    with open(SCOREFILE,"w") as f:
        for n,sc in s: f.write(f"{n},{sc}\n")

def calc_grade(hits, misses):
    total = hits+misses
    if total == 0: return "D"
    acc = 100*hits/total
    for thr,g in GRADE_THRESHOLDS:
        if acc >= thr: return g
    return "D"

# ===== SKINURI  (doar date de culoare) =====

SKINS = {
    "clasic": {
        "name":"CLASIC","desc":"Stilul original","locked":False,
        "bg_top":(10,10,30),"bg_bot":(20,20,55),"panel_top":(25,25,55),"panel_bot":(15,15,40),
        "panel_line":(220,50,50),
        "target1":(220,50,50),"target1_rim":(255,120,120),"target1_in":(255,255,255),
        "targetN":(255,140,0),"targetN_rim":(255,200,80),
        "bomb":(18,12,28),"bomb_ring":(160,0,220),"bomb_glow":(140,0,200),"bomb_txt":(220,0,220),
        "crosshair":(255,255,255),"crosshair_dot":(255,50,50),
        "text_main":(60,220,60),"text_sub":(200,210,255),"text_dim":(130,140,180),
        "combo":(255,220,0),"bar_bg":(20,20,45),"bar_fill":(50,200,50),
        "particle_colors":[(220,50,50),(255,140,0),(255,255,255)],"grid":True,"grid_color":(255,255,255)},
    "armata": {
        "name":"ARMATA","desc":"Camuflaj militar","locked":False,
        "bg_top":(18,28,10),"bg_bot":(32,50,18),"panel_top":(15,25,8),"panel_bot":(10,18,5),
        "panel_line":(130,170,60),
        "target1":(180,50,30),"target1_rim":(230,100,60),"target1_in":(240,200,150),
        "targetN":(200,130,20),"targetN_rim":(240,180,60),
        "bomb":(10,10,5),"bomb_ring":(80,160,40),"bomb_glow":(60,140,30),"bomb_txt":(150,230,90),
        "crosshair":(180,220,100),"crosshair_dot":(255,255,100),
        "text_main":(140,200,60),"text_sub":(200,220,160),"text_dim":(110,140,70),
        "combo":(220,200,80),"bar_bg":(20,35,10),"bar_fill":(100,160,40),
        "particle_colors":[(180,50,30),(200,130,20),(140,200,60)],"grid":True,"grid_color":(100,140,60)},
    "romania": {
        "name":"ROMANIA","desc":"Tricolor national","locked":False,
        "bg_top":(8,8,22),"bg_bot":(18,18,40),"panel_top":(8,8,22),"panel_bot":(5,5,15),
        "panel_line":(0,90,200),
        "target1":(200,20,30),"target1_rim":(240,80,80),"target1_in":(255,220,0),
        "targetN":(255,180,0),"targetN_rim":(255,220,100),
        "bomb":(10,10,20),"bomb_ring":(0,90,200),"bomb_glow":(0,70,180),"bomb_txt":(80,150,255),
        "crosshair":(255,220,0),"crosshair_dot":(200,20,30),
        "text_main":(255,220,0),"text_sub":(200,220,255),"text_dim":(110,130,170),
        "combo":(200,20,30),"bar_bg":(15,15,40),"bar_fill":(0,90,200),
        "particle_colors":[(200,20,30),(255,220,0),(0,90,200)],"grid":False,"tricolor":True},
    "neon": {
        "name":"NEON","desc":"Cyberpunk glitch","locked":False,
        "bg_top":(2,0,10),"bg_bot":(8,0,22),"panel_top":(3,0,12),"panel_bot":(1,0,6),
        "panel_line":(0,255,200),
        "target1":(255,0,100),"target1_rim":(255,100,180),"target1_in":(0,255,200),
        "targetN":(255,200,0),"targetN_rim":(255,240,100),
        "bomb":(5,0,15),"bomb_ring":(255,0,200),"bomb_glow":(200,0,160),"bomb_txt":(255,100,255),
        "crosshair":(0,255,200),"crosshair_dot":(255,0,100),
        "text_main":(0,255,200),"text_sub":(200,150,255),"text_dim":(90,70,140),
        "combo":(255,0,150),"bar_bg":(15,0,35),"bar_fill":(0,255,200),
        "particle_colors":[(255,0,100),(0,255,200),(255,200,0)],"grid":True,"grid_color":(0,255,200)},
    "desert": {
        "name":"DESERT","desc":"Nisip si soare","locked":False,
        "bg_top":(160,120,60),"bg_bot":(200,160,90),"panel_top":(130,95,45),"panel_bot":(100,70,30),
        "panel_line":(120,60,20),
        "target1":(160,40,20),"target1_rim":(210,90,50),"target1_in":(240,220,180),
        "targetN":(180,100,10),"targetN_rim":(230,160,60),
        "bomb":(50,30,10),"bomb_ring":(120,60,20),"bomb_glow":(100,50,15),"bomb_txt":(240,200,120),
        "crosshair":(50,25,8),"crosshair_dot":(200,60,20),
        "text_main":(70,25,8),"text_sub":(55,28,10),"text_dim":(90,65,35),
        "combo":(160,60,10),"bar_bg":(120,90,50),"bar_fill":(160,60,20),
        "particle_colors":[(160,40,20),(180,100,10),(240,200,120)],"grid":False},
    "legendar": {
        "name":"LEGENDAR","desc":"Deblocat dupa primul joc complet!","locked":True,
        "unlock_hint":"Termina un joc pentru a debloca!",
        "bg_top":(4,2,0),"bg_bot":(10,6,0),"panel_top":(14,9,0),"panel_bot":(8,4,0),
        "panel_line":(255,200,0),
        "target1":(255,180,0),"target1_rim":(255,230,100),"target1_in":(255,255,200),
        "targetN":(255,120,0),"targetN_rim":(255,180,80),
        "bomb":(20,10,0),"bomb_ring":(255,60,0),"bomb_glow":(220,80,0),"bomb_txt":(255,200,100),
        "crosshair":(255,215,0),"crosshair_dot":(255,100,0),
        "text_main":(255,210,0),"text_sub":(255,230,150),"text_dim":(170,130,50),
        "combo":(255,100,0),"bar_bg":(25,15,0),"bar_fill":(255,200,0),
        "particle_colors":[(255,180,0),(255,120,0),(255,255,200)],"grid":False,"legendar":True},
}
SKIN_ORDER = ["clasic","armata","romania","neon","desert","legendar"]
current_skin_idx = 0
def get_skin(): return SKINS[SKIN_ORDER[current_skin_idx]]

# ===== ENTITATI  (Target / Bomb / PowerUp impart aceeasi baza) =====

class Entity:
    """Baza comuna: pozitie, miscare cu ricoseu, durata de viata, coliziune."""
    is_bomb = False
    is_powerup = False
    n = 1
    def __init__(self, r, speed, life):
        self.r = r
        self.x = random.randint(r, W-r); self.y = random.randint(r, GAME_H-r)
        a = random.uniform(0, 6.28)
        self.vx = math.cos(a)*speed; self.vy = math.sin(a)*speed
        self.born = time.time(); self.lifetime = life
        self.t = random.uniform(0, 6.28)            # cronometru intern pt animatii

    def update(self, dt):
        self.x += self.vx*dt; self.y += self.vy*dt
        if self.x-self.r < 0:      self.x = self.r;      self.vx *= -1   # ricoseu pereti
        elif self.x+self.r > W:    self.x = W-self.r;    self.vx *= -1
        if self.y-self.r < 0:      self.y = self.r;      self.vy *= -1
        elif self.y+self.r > GAME_H: self.y = GAME_H-self.r; self.vy *= -1
        self.t += dt*3

    def alive(self): return time.time()-self.born < self.lifetime
    def hit(self, mx, my): return (mx-self.x)**2+(my-self.y)**2 <= self.r**2
    def age(self): return min(1.0, (time.time()-self.born)/self.lifetime)

    def _life_bar(self, surf, col, bg):
        draw_progress_bar(surf, (int(self.x)-self.r, int(self.y)+self.r+4, self.r*2, 4),
                          1-self.age(), col, bg, radius=2, glow=False)

class Target(Entity):
    def __init__(self, lvl):
        n = random.randint(2,5) if random.random() < MULTI_CHANCE else 1
        r = RN if n > 1 else R1
        speed = lvl["speed"]*SPEED_MULT * (1.0/n if n > 1 else 1)        # tintele multiple sunt mai lente
        life  = lvl["target_time"] / (n*0.5 if n > 1 else 1)
        super().__init__(r, speed, life); self.n = n

    def draw(self, surf):
        skin = get_skin(); age = self.age(); cx, cy = int(self.x), int(self.y)
        if skin.get("legendar"): self._draw_legendar(surf, cx, cy); return
        if self.n == 1:
            c = safe_color3(skin["target1"]); rim = safe_color3(skin["target1_rim"]); inn = safe_color3(skin["target1_in"])
            draw_glow_circle(surf, c, (cx,cy), self.r, alpha=50, layers=3)
            for i in range(self.r,0,-1):                                  # umplere radiala
                t = i/self.r
                pygame.draw.circle(surf, tuple(int(c[j]*t+inn[j]*(1-t)*0.15) for j in range(3)), (cx,cy), i)
            pygame.draw.circle(surf, rim, (cx,cy), self.r, 2)
            hl = int(self.r*0.55)                                         # cruce centrala (tinta)
            pygame.draw.line(surf, inn, (cx-hl,cy), (cx+hl,cy), 1)
            pygame.draw.line(surf, inn, (cx,cy-hl), (cx,cy+hl), 1)
            pygame.draw.circle(surf, inn, (cx,cy), 3)
        else:
            c = safe_color3(skin["targetN"]); rim = safe_color3(skin["targetN_rim"])
            draw_glow_circle(surf, c, (cx,cy), self.r, alpha=40, layers=3)
            for i in range(self.r,0,-1):
                t = i/self.r
                pygame.draw.circle(surf, tuple(int(c[j]*t+max(0,c[j]-60)*(1-t)) for j in range(3)), (cx,cy), i)
            pygame.draw.circle(surf, rim, (cx,cy), self.r, 2)
            txt = font_small.render(str(self.n), True, WHITE)
            surf.blit(txt, (cx-txt.get_width()//2, cy-txt.get_height()//2))
        self._life_bar(surf, (220,50,50) if age > 0.7 else safe_color3(skin["bar_fill"]), skin["bar_bg"])

    def _draw_legendar(self, surf, cx, cy):
        t = self.t; pulse = 0.5+0.5*math.sin(t)
        for layer in range(5,0,-1):                                       # halou auriu pulsant
            r = self.r+layer*3+int(5*pulse)
            gs = pygame.Surface((r*2+2,r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (255,int(150+50*pulse),0,int(35*(1-layer/5)*pulse)), (r+1,r+1), r)
            surf.blit(gs, (cx-r-1,cy-r-1))
        for i in range(self.r,0,-1):
            t2 = i/self.r
            pygame.draw.circle(surf, (int(60*t2+20*(1-t2)), int(40*t2+20*(1-t2)), 0), (cx,cy), i)
        pygame.draw.circle(surf, (255,200,0), (cx,cy), self.r, 2)
        if self.n == 1:
            for i in range(8):                                           # spite rotative
                a = t+i*math.pi/4
                pygame.draw.line(surf, (255,220,80),
                    (cx+int(self.r*0.35*math.cos(a)), cy+int(self.r*0.35*math.sin(a))),
                    (cx+int((self.r-3)*math.cos(a)), cy+int((self.r-3)*math.sin(a))), 2)
            pygame.draw.circle(surf, (255,255,200), (cx,cy), 4)
        else:
            txt = font_small.render(str(self.n), True, (255,235,100))
            surf.blit(txt, (cx-txt.get_width()//2, cy-txt.get_height()//2))
        self._life_bar(surf, (255,200,0), (30,20,0))

class Bomb(Entity):
    is_bomb = True
    def __init__(self, lvl):
        super().__init__(BOMB_R, lvl["speed"]*SPEED_MULT*0.58, lvl["target_time"]*1.5)

    def draw(self, surf):
        skin = get_skin(); age = self.age(); cx, cy = int(self.x), int(self.y)
        gc = safe_color3(skin["bomb_glow"]); rc = safe_color3(skin["bomb_ring"]); pulse = abs(math.sin(self.t))
        for layer in range(5,0,-1):                                       # halou de avertizare
            r = self.r+layer*3+int(4*pulse)
            gs = pygame.Surface((r*2+2,r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*gc, int(30*(1-layer/5)*pulse)), (r+1,r+1), r)
            surf.blit(gs, (cx-r-1,cy-r-1))
        base = safe_color3(skin["bomb"])
        for i in range(self.r,0,-1):
            t = i/self.r
            pygame.draw.circle(surf, (int(base[0]*t+30*(1-t)), int(base[1]*t), int(base[2]*t+20*(1-t))), (cx,cy), i)
        pygame.draw.circle(surf, rc, (cx,cy), self.r, 2+int(pulse))
        ts = font_med.render("!", True, safe_color3(skin["bomb_txt"]))
        surf.blit(ts, (cx-ts.get_width()//2, cy-ts.get_height()//2))
        self._life_bar(surf, (220,50,20) if age <= 0.65 else (255,int(50*(1-pulse)),0), (30,10,10))

class PowerUp(Entity):
    is_powerup = True
    def __init__(self, lvl):
        super().__init__(POWERUP_R, lvl["speed"]*SPEED_MULT*0.45, lvl["target_time"]*2.2)
        self.ptype = random.choice(list(POWERUP_TYPES))

    def draw(self, surf):
        info = POWERUP_TYPES[self.ptype]; age = self.age(); cx, cy = int(self.x), int(self.y)
        c = safe_color3(info["color"]); gc = safe_color3(info["glow"])
        pr = int(5*abs(math.sin(self.t)))
        for layer in range(4,0,-1):                                       # halou colorat
            r = self.r+pr+layer*3
            gs = pygame.Surface((r*2+2,r*2+2), pygame.SRCALPHA)
            pygame.draw.circle(gs, (*gc, 25//layer), (r+1,r+1), r)
            surf.blit(gs, (cx-r-1,cy-r-1))
        draw_rounded_rect_gradient(surf, tuple(min(255,v+40) for v in c), tuple(max(0,v-30) for v in c),
                                   (cx-self.r,cy-self.r,self.r*2,self.r*2), radius=self.r)
        pygame.draw.circle(surf, c, (cx,cy), self.r, 2)
        for i in range(6):                                                # puncte orbitante
            a = self.t*1.2+i*math.pi/3
            ds = pygame.Surface((6,6), pygame.SRCALPHA)
            pygame.draw.circle(ds, (*c, int(180+75*math.sin(self.t*2+i))), (3,3), 2)
            surf.blit(ds, (cx+int((self.r+2)*math.cos(a))-3, cy+int((self.r+2)*math.sin(a))-3))
        lbl = font_small.render(info["label"], True, WHITE)
        surf.blit(lbl, (cx-lbl.get_width()//2, cy-lbl.get_height()//2))
        draw_progress_bar(surf, (cx-self.r, cy+self.r+5, self.r*2, 5), 1-age, c, (20,20,40), radius=2, glow=False)

# ===== EFECTE  (particule + text plutitor) =====

class HitParticle:
    def __init__(self, x, y, color):
        self.x, self.y = x, y; self.color = safe_color3(color)
        a = random.uniform(0,6.28); sp = random.uniform(40,130)
        self.vx = math.cos(a)*sp; self.vy = math.sin(a)*sp - random.uniform(20,60)
        self.born = time.time(); self.lifetime = random.uniform(0.3,0.7); self.size = random.uniform(2,5)
    def update(self, dt): self.x += self.vx*dt; self.y += self.vy*dt; self.vy += 200*dt
    def alive(self): return time.time()-self.born < self.lifetime
    def draw(self, surf):
        age = min(1.0, (time.time()-self.born)/self.lifetime); s = int(self.size*(1-age*0.5))
        if s <= 0: return
        ps = pygame.Surface((s*2+2,s*2+2), pygame.SRCALPHA)
        pygame.draw.circle(ps, (*self.color, int(255*(1-age))), (s+1,s+1), s)
        surf.blit(ps, (int(self.x)-s, int(self.y)-s))

class FloatText:
    def __init__(self, x, y, text, color, big=False):
        self.x, self.y, self.text = x, y, text; self.color = safe_color3(color)
        self.born = time.time(); self.lifetime = 0.9; self.vy = -55; self.big = big
    def update(self, dt): self.y += self.vy*dt; self.vy *= 0.96
    def alive(self): return time.time()-self.born < self.lifetime
    def draw(self, surf):
        age = min(1.0, (time.time()-self.born)/self.lifetime)
        f = font_med if self.big else font_small
        txt = f.render(self.text, True, self.color)
        if self.big:
            sc = 1.0+0.3*(1-age)
            txt = pygame.transform.smoothscale(txt, (int(txt.get_width()*sc), int(txt.get_height()*sc)))
        txt.set_alpha(int(255*(1-age**1.5)))
        surf.blit(txt, (int(self.x)-txt.get_width()//2, int(self.y)))

# ===== HUD  (combo / powerup / frenzy / notificari / crosshair) =====

def get_combo_color(combo):
    if combo >= 10: return (255,50,50)
    if combo >= 5:  return (255,180,0)
    return safe_color3(get_skin()["combo"])

def get_combo_multiplier(combo): return 1+combo//5     # x2 la 5, x3 la 10, etc.

def draw_combo(surf, combo, flash):
    if combo <= 0: return
    color = get_combo_color(combo)
    draw_glass_panel(surf, (8,8,175,65), color=(20,15,40), alpha=160, border_color=color, radius=10)
    txt = font_combo.render(f"COMBO  x{combo}", True, color)
    if flash > 0:
        sc = 1.0+0.08*(flash/0.15)
        txt = pygame.transform.smoothscale(txt, (int(txt.get_width()*sc), int(txt.get_height()*sc)))
    surf.blit(txt, (12+(175-txt.get_width())//2, 12))
    m = get_combo_multiplier(combo)
    if m >= 2:
        surf.blit(font_tiny.render(f"  x{m} SCOR", True, (255,255,120)), (14,48))

def draw_active_powerup(surf, active, timer):
    if not active: return
    info = POWERUP_TYPES[active]; bw, bh = 190, 50; bx, by = W-bw-10, 10
    draw_glass_panel(surf, (bx,by,bw,bh), color=(15,10,35), alpha=180, border_color=info["color"], radius=10)
    lbl = font_small.render(info["desc"], True, safe_color3(info["color"]))
    surf.blit(lbl, (bx+(bw-lbl.get_width())//2, by+7))
    draw_progress_bar(surf, (bx+8,by+32,bw-16,8), timer/info["duration"], info["color"], (20,15,40), radius=4)

def draw_frenzy_hud(surf, timer):
    if timer <= 0: return
    txt = font_combo.render(f"FRENZY!  {timer:.1f}s", True, (255,120,0))
    sh = font_combo.render(f"FRENZY!  {timer:.1f}s", True, (80,30,0)); sh.set_alpha(120)
    surf.blit(sh, (W//2-sh.get_width()//2+2, 16))
    txt.set_alpha(int(210+45*math.sin(time.time()*6)))
    surf.blit(txt, (W//2-txt.get_width()//2, 14))

class NotificationQueue:
    def __init__(self): self.queue=[]; self.current=None; self.timer=0.0; self.color=WHITE
    def add(self, text, color=(255,220,0)): self.queue.append((text, safe_color3(color)))
    def update(self, dt):
        if self.current is None and self.queue: self.current, self.color = self.queue.pop(0); self.timer = 2.8
        if self.current:
            self.timer -= dt
            if self.timer <= 0: self.current = None
    def draw(self, surf):
        if not self.current: return
        a = 255 if self.timer > 0.5 else int(255*self.timer/0.5)
        w, h = 360, 46; x, y = W//2-w//2, GAME_H-66
        draw_glass_panel(surf, (x,y,w,h), color=(15,12,30), alpha=190, border_color=self.color, radius=10)
        txt = font_small.render(self.current, True, self.color); txt.set_alpha(a)
        surf.blit(txt, (W//2-txt.get_width()//2, y+15))

def draw_crosshair(surf, skin, mx, my, active=None):
    c = safe_color3(skin["crosshair"]); dot = safe_color3(skin.get("crosshair_dot", skin["crosshair"]))
    if active in ("freeze","slow","double"):       # crosshair-ul ia culoarea powerup-ului
        c, dot = {"freeze":((100,210,255),(0,160,255)),"slow":((190,110,255),(130,0,255)),
                  "double":((255,225,0),(255,170,0))}[active]
    gs = pygame.Surface((44,44), pygame.SRCALPHA); pygame.draw.circle(gs, (*c,18), (22,22), 18); surf.blit(gs, (mx-22,my-22))
    g, l = 6, 14
    pygame.draw.line(surf, c, (mx-g-l,my), (mx-g,my), 2); pygame.draw.line(surf, c, (mx+g,my), (mx+g+l,my), 2)
    pygame.draw.line(surf, c, (mx,my-g-l), (mx,my-g), 2); pygame.draw.line(surf, c, (mx,my+g), (mx,my+g+l), 2)
    pygame.draw.circle(surf, c, (mx,my), 14, 1); pygame.draw.circle(surf, dot, (mx,my), 3)

# ===== ECRANE =====

def _quit_events():
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT: pygame.quit(); exit()
        yield ev

def show_countdown():
    # 3..2..1..GO! inainte de inceperea jocului
    clock = pygame.time.Clock(); skin = get_skin(); _init_bg_particles(40)
    for i in range(3,0,-1):
        start = time.time()
        while time.time()-start < 1.0:
            dt = clock.tick(60)/1000.0; pr = time.time()-start
            draw_gradient_rect(screen, skin["bg_top"], skin["bg_bot"], (0,0,W,GAME_H))
            _update_bg_particles(dt, skin["particle_colors"]); _draw_bg_particles(screen, skin["particle_colors"])
            draw_gradient_rect(screen, skin["panel_top"], skin["panel_bot"], (0,GAME_H,W,PANEL_H))
            cr = int(80*(2.0-pr))
            if cr > 0:
                cs = pygame.Surface((cr*2,cr*2), pygame.SRCALPHA)
                pygame.draw.circle(cs, (255,220,0,int(60*(1-pr))), (cr,cr), cr); screen.blit(cs, (W//2-cr,GAME_H//2-cr))
            f = _f(int(60+20*(1-pr))); num = f.render(str(i), True, (255,int(220*(1-pr*0.3)),0))
            screen.blit(num, (W//2-num.get_width()//2, GAME_H//2-num.get_height()//2))
            r = font_med.render("Pregateste-te!", True, skin["text_dim"])
            screen.blit(r, (W//2-r.get_width()//2, GAME_H//2+55))
            pygame.display.flip()
            list(_quit_events())
    start = time.time()
    while time.time()-start < 0.65:
        pr = (time.time()-start)/0.65; screen.fill(BLACK)
        draw_gradient_rect(screen, skin["bg_top"], skin["bg_bot"], (0,0,W,GAME_H))
        go = _f(int(72+30*pr)).render("GO!", True, (60,230,60)); go.set_alpha(int(255*(1-pr)))
        screen.blit(go, (W//2-go.get_width()//2, GAME_H//2-go.get_height()//2))
        pygame.display.flip(); clock.tick(60); list(_quit_events())

def show_unlock_screen(sounds):
    # Ecran festiv cand se deblocheaza skinul Legendar
    clock = pygame.time.Clock(); t = 0.0; dur = 5.0
    parts = [{"x":random.uniform(0,W),"y":random.uniform(H,H+250),"vx":random.uniform(-20,20),
        "vy":random.uniform(-180,-80),"size":random.uniform(1.5,5),"alpha":0,"tw":random.uniform(0,6.28)} for _ in range(100)]
    play_sfx(sounds, "unlock")
    while t < dur:
        dt = clock.tick(60)/1000.0; t += dt; pr = t/dur
        for p in parts:
            p["x"] += p["vx"]*dt; p["y"] += p["vy"]*dt; p["tw"] += 4*dt; p["alpha"] = min(255,int(255*min(pr*3,1)))
            if p["y"] < -10: p["y"] = H+random.uniform(0,60); p["x"] = random.uniform(0,W)
        draw_gradient_rect(screen, (4,2,0), (10,6,0), (0,0,W,H))
        for r in range(240,0,-24):
            a = int(25*math.sin(math.pi*pr)*(1-r/240))
            if a > 0:
                gs = pygame.Surface((r*2,r*2), pygame.SRCALPHA); pygame.draw.circle(gs, (255,150,0,a), (r,r), r)
                screen.blit(gs, (W//2-r,H//2-r))
        for p in parts:
            a = int(p["alpha"]*(0.5+0.5*math.sin(p["tw"]))); sr = p["size"]
            ps = pygame.Surface((int(sr*2+2),int(sr*2+2)), pygame.SRCALPHA)
            pygame.draw.circle(ps, (255,int(180*(a/255)),0,a), (int(sr+1),int(sr+1)), int(sr+0.5))
            screen.blit(ps, (int(p["x"]-sr),int(p["y"]-sr)))
        ta = int(255*min(pr*2,1))
        for txt, col, dy, f in [("*** SKIN DEBLOCAT! ***",(255,210,0),-90,font_title),
                                ("LEGENDAR",(255,185,0),-20,_f(52)),
                                ("Disponibil acum in Skinuri",(200,155,50),48,font_med)]:
            s = f.render(txt, True, col); s.set_alpha(ta); screen.blit(s, (W//2-s.get_width()//2, H//2+dy))
        sk = font_tiny.render("apasa orice tasta pentru a continua", True, (90,70,20))
        screen.blit(sk, (W//2-sk.get_width()//2, H-38))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN): return

def show_results_screen(score, hits, misses, max_combo, new_ach, best_before):
    grade = calc_grade(hits, misses); gcol = GRADE_COLORS[grade]
    total = hits+misses; acc = int(100*hits/total) if total else 0
    is_best = score > best_before; clock = pygame.time.Clock(); t = 0.0
    while True:
        t += clock.tick(60)/1000.0; skin = get_skin()
        draw_gradient_rect(screen, (10,8,22), (18,14,36), (0,0,W,H))
        title = font_big.render("REZULTATE", True, skin["text_sub"]); screen.blit(title, (W//2-title.get_width()//2, 22))
        pygame.draw.line(screen, safe_color3(skin["panel_line"]), (50,62), (W-50,62), 1)
        # Medalion grad
        gf = _f(int(90*(1.0+0.07*math.sin(t*2.8)))); gt = gf.render(grade, True, gcol)
        draw_glow_circle(screen, gcol, (95,145), 62, alpha=55, layers=4)
        pygame.draw.circle(screen, gcol, (95,145), 66, 2)
        screen.blit(gt, (95-gt.get_width()//2, 145-gt.get_height()//2))
        lbl = font_tiny.render("GRAD", True, gcol); screen.blit(lbl, (95-lbl.get_width()//2, 200))
        # Tabel statistici
        sx, sy, lh = 185, 75, 40
        rows = [("Scor final",str(score),skin["text_main"]),("Tinte lovite",str(hits),(80,220,80)),
                ("Tinte ratate",str(misses),(220,80,80)),("Acuratete",f"{acc}%",gcol),
                ("Combo maxim",f"x{max_combo}",(255,180,0))]
        for i,(lb,val,col) in enumerate(rows):
            y = sy+i*lh; c = safe_color3(col)
            draw_glass_panel(screen, (sx,y-2,W-sx-30,36), color=(18,14,32), alpha=150, border_color=c, radius=7)
            screen.blit(font_small.render(lb, True, (130,125,165)), (sx+10,y+8))
            v = font_med.render(val, True, c); screen.blit(v, (W-50-v.get_width(),y+7))
        if is_best:
            bt = font_small.render("*** NOU RECORD PERSONAL! ***", True, (255,215,0))
            bt.set_alpha(int(210+45*math.sin(t*3.5))); screen.blit(bt, (sx,sy+5*lh+8))
        pygame.draw.line(screen, (50,42,78), (30,310), (W-30,310), 1)
        # Achievements noi
        ay = 320
        if new_ach:
            screen.blit(font_small.render("ACHIEVEMENT-URI DEBLOCATE", True, (255,195,50)), (35,ay)); ay += 26
            for a in new_ach[:3]:
                draw_glass_panel(screen, (35,ay,W-70,32), color=(25,18,5), alpha=160, border_color=(180,140,30), radius=7)
                screen.blit(font_small.render(f"  {a['icon']}  {a['name']}  --  {a['desc']}", True, (210,175,65)), (40,ay+8)); ay += 36
        else:
            screen.blit(font_small.render("Niciun achievement nou.", True, (70,65,95)), (35,ay))
        tips = {"D":"Concentreaza-te pe precizie! Evita click-urile gresite.","C":"Bine! Urmareste combo-urile.",
                "B":"Solid! Incearca sa nu ratezi la inceput de nivel.","A":"Excelent! Esti aproape de perfectiune.",
                "S":"Extraordinar! Mai poti da si mai bine?","SS":"PERFECT! Esti la un nivel aparte!"}
        screen.blit(font_tiny.render(f"Sfat: {tips[grade]}", True, (85,80,115)), (35,H-60))
        pygame.draw.line(screen, (50,42,78), (30,H-72), (W-30,H-72), 1)
        hint = font_med.render("ENTER  --  meniu       ESC  --  iesire", True, (100,95,140))
        screen.blit(hint, (W//2-hint.get_width()//2, H-44))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN: return True
                if ev.key == pygame.K_ESCAPE: pygame.quit(); exit()

def _list_screen(title_txt, build_rows, footer, line_h=48, top=80):
    # Sablon comun pentru ecranele tip lista (statistici/achievements)
    clock = pygame.time.Clock()
    while True:
        draw_gradient_rect(screen, (8,6,18), (14,11,28), (0,0,W,H))
        title = font_big.render(title_txt, True, (200,200,255)); screen.blit(title, (W//2-title.get_width()//2, 22))
        pygame.draw.line(screen, (60,50,100), (40,65), (W-40,65), 1)
        build_rows()
        screen.blit(font_small.render(footer, True, (80,70,110)), (W//2-200, H-40))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE: return
        clock.tick(30)

def show_statistics():
    stats = load_stats(); total = stats["total_hits"]+stats["total_misses"]
    acc = int(100*stats["total_hits"]/total) if total else 0
    rows = [("Jocuri jucate",str(stats["total_games"]),(180,180,255)),("Tinte lovite",str(stats["total_hits"]),(80,220,80)),
            ("Tinte ratate",str(stats["total_misses"]),(220,80,80)),("Bombe lovite",str(stats["total_bombs_hit"]),(220,80,80)),
            ("Acuratete globala",f"{acc}%",(255,200,50)),("Combo maxim",f"x{stats['max_combo']}",(255,180,0)),
            ("Scor record",str(stats["best_score"]),(255,215,0)),("Frenzy activat",f"{stats.get('frenzy_count',0)}x",(255,120,0)),
            ("Jocuri fara bombe",str(stats.get("no_bomb_games",0)),(100,220,220))]
    def build():
        for i,(lb,val,col) in enumerate(rows):
            y = 80+i*48; c = safe_color3(col)
            draw_glass_panel(screen, (38,y,W-76,40), color=(18,14,32), alpha=170, border_color=c, radius=8)
            screen.blit(font_small.render(lb, True, (130,122,168)), (54,y+10))
            v = font_med.render(val, True, c); screen.blit(v, (W-60-v.get_width(),y+9))
    _list_screen("STATISTICI", build, "ESC  --  inapoi")

def show_achievements():
    stats = load_stats(); clock = pygame.time.Clock(); scroll = 0
    while True:
        draw_gradient_rect(screen, (8,6,18), (14,11,28), (0,0,W,H))
        title = font_big.render("ACHIEVEMENTS", True, (200,200,255)); screen.blit(title, (W//2-title.get_width()//2, 22))
        pygame.draw.line(screen, (60,50,100), (40,65), (W-40,65), 1)
        for i,a in enumerate(ACHIEVEMENTS):
            y = 80+i*56+scroll
            if y < 60 or y > H-50: continue
            on = a["id"] in stats["unlocked_achievements"]
            draw_glass_panel(screen, (38,y,W-76,48), color=(28,22,48) if on else (16,13,26),
                             alpha=180, border_color=(100,80,160) if on else (38,32,58), radius=9)
            screen.blit(font_med.render(a["icon"], True, (255,200,50) if on else (70,62,90)), (54,y+12))
            screen.blit(font_small.render(a["name"], True, WHITE if on else (70,62,95)), (88,y+8))
            screen.blit(font_tiny.render(a["desc"], True, (155,135,200) if on else (55,50,78)), (88,y+28))
            screen.blit(font_tiny.render("DEBLOCAT" if on else "BLOCAT", True, (70,200,70) if on else (70,62,90)), (W-160,y+18))
        nu = len(stats["unlocked_achievements"])
        screen.blit(font_small.render(f"Progres:  {nu} / {len(ACHIEVEMENTS)}", True, (110,95,155)), (40,H-42))
        draw_progress_bar(screen, (40,H-24,W-80,6), nu/len(ACHIEVEMENTS), (130,100,220), (30,24,50), radius=3)
        screen.blit(font_small.render("ESC  --  inapoi    sus/jos = scroll", True, (80,70,110)), (W-260,H-42))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE: return
                if ev.key == pygame.K_UP: scroll = min(0, scroll+20)
                if ev.key == pygame.K_DOWN: scroll = max(-(len(ACHIEVEMENTS)*56-380), scroll-20)
        clock.tick(30)

def show_scoreboard():
    scores = load_scores(); clock = pygame.time.Clock(); medals = [(255,215,0),(210,210,210),(205,127,50)]
    while True:
        draw_gradient_rect(screen, (8,6,18), (14,11,28), (0,0,W,H))
        title = font_big.render("SCOREBOARD", True, (200,200,255)); screen.blit(title, (W//2-title.get_width()//2, 22))
        pygame.draw.line(screen, (60,50,100), (40,65), (W-40,65), 1)
        for i,(n,s) in enumerate(scores[:10]):
            y = 82+i*44; mc = medals[i] if i < 3 else (80,75,120)
            draw_glass_panel(screen, (40,y,W-80,38), color=(18,14,32) if i<3 else (14,11,24), alpha=175, border_color=mc, radius=8)
            if i < 3:
                pygame.draw.circle(screen, mc, (62,y+19), 10)
                mn = font_tiny.render(str(i+1), True, BLACK); screen.blit(mn, (62-mn.get_width()//2,y+19-mn.get_height()//2))
            else:
                screen.blit(font_small.render(str(i+1), True, (80,75,120)), (55,y+10))
            nt = font_med.render(n, True, mc if i<3 else (160,155,200))
            st = font_med.render(str(s), True, mc if i<3 else (130,125,175))
            screen.blit(nt, (82,y+9)); screen.blit(st, (W-60-st.get_width(),y+9))
        screen.blit(font_small.render("ESC  --  inapoi", True, (80,70,110)), (W//2-60, H-38))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE: return
        clock.tick(30)

def _preview_skin(psf, skin, pw, ph, pp):
    # Deseneaza un mic exemplu de skin (fundal + 2 tinte + bomba + crosshair)
    if skin.get("legendar"):
        draw_gradient_rect(psf, (4,2,0), (10,6,0), (0,0,pw,ph))
        for _ in range(25):
            pygame.draw.circle(psf, (255,random.randint(140,220),0), (random.randint(0,pw),random.randint(0,ph)), random.randint(1,3))
    else:
        draw_gradient_rect(psf, skin["bg_top"], skin["bg_bot"], (0,0,pw,ph))
        if skin.get("grid"):
            gc = tuple(c//6 for c in skin.get("grid_color",(200,200,200)))
            for x in range(0,pw,50): pygame.draw.line(psf, gc, (x,0), (x,ph), 1)
            for y in range(0,ph,50): pygame.draw.line(psf, gc, (0,y), (pw,y), 1)
        if skin.get("tricolor"):
            for i,col in enumerate([(0,70,160),(255,210,0),(190,20,30)]):
                s = pygame.Surface((7,ph), pygame.SRCALPHA); s.fill((*col,50)); psf.blit(s, (pw-7*(3-i),0))
    # tinta simpla
    c1 = safe_color3(skin["target1"]); i1 = safe_color3(skin["target1_in"])
    for i in range(R1,0,-1):
        t = i/R1; pygame.draw.circle(psf, tuple(int(c1[j]*t+i1[j]*(1-t)*0.1) for j in range(3)), (105,105), i)
    pygame.draw.circle(psf, safe_color3(skin["target1_rim"]), (105,105), R1, 2); pygame.draw.circle(psf, i1, (105,105), 3)
    # tinta multipla
    c2 = safe_color3(skin["targetN"])
    for i in range(RN,0,-1):
        t = i/RN; pygame.draw.circle(psf, tuple(int(c2[j]*t+max(0,c2[j]-50)*(1-t)) for j in range(3)), (200,160), i)
    pygame.draw.circle(psf, safe_color3(skin["targetN_rim"]), (200,160), RN, 2)
    l3 = font_small.render("3", True, WHITE); psf.blit(l3, (200-l3.get_width()//2,160-l3.get_height()//2))
    # bomba
    base = safe_color3(skin["bomb"])
    for i in range(BOMB_R,0,-1):
        t = i/BOMB_R; pygame.draw.circle(psf, tuple(int(base[j]*t) for j in range(3)), (295,100), i)
    pygame.draw.circle(psf, safe_color3(skin["bomb_ring"]), (295,100), BOMB_R, 2)
    bt = font_small.render("!", True, safe_color3(skin["bomb_txt"])); psf.blit(bt, (295-bt.get_width()//2,100-bt.get_height()//2))
    # crosshair
    cc = safe_color3(skin["crosshair"])
    for dx,dy in [(-18,0),(6,0),(0,-18),(0,6)]:
        pygame.draw.line(psf, cc, (155+dx,210+dy), (155+(dx+12 if dx else 0),210+(dy+12 if dy else 0)), 1)
    pygame.draw.circle(psf, cc, (155,210), 12, 1)
    pygame.draw.circle(psf, safe_color3(skin.get("crosshair_dot",skin["crosshair"])), (155,210), 3)
    draw_progress_bar(psf, (16,ph-26,pw-32,10), 0.65, skin["bar_fill"], skin["bar_bg"], radius=5)

def show_skin_select():
    global current_skin_idx
    clock = pygame.time.Clock(); pp = 0.0
    while True:
        pp += clock.tick(60)/1000.0*2.5
        draw_gradient_rect(screen, (8,6,18), (14,11,28), (0,0,W,H))
        title = font_big.render("SELECTEAZA SKIN", True, (200,200,255)); screen.blit(title, (W//2-title.get_width()//2, 22))
        pygame.draw.line(screen, (60,50,100), (40,65), (W-40,65), 1)
        hint = font_small.render("< >  navigare     ENTER  confirma     ESC  inapoi", True, (80,75,115))
        screen.blit(hint, (W//2-hint.get_width()//2, H-35))
        key = SKIN_ORDER[current_skin_idx]; skin = SKINS[key]; unlocked = is_skin_unlocked(key)
        px, py, pw, ph = 200, 80, 400, 310
        psf = pygame.Surface((pw,ph), pygame.SRCALPHA)
        if unlocked:
            _preview_skin(psf, skin, pw, ph, pp)
            screen.blit(psf, (px,py))
            bdc = (int(200+55*math.sin(pp)),int(150+50*math.sin(pp*0.7)),0) if skin.get("legendar") else safe_color3(skin["panel_line"])
            pygame.draw.rect(screen, bdc, (px,py,pw,ph), 2, border_radius=10)
            nm = font_big.render(skin["name"], True, (255,210,0) if skin.get("legendar") else safe_color3(skin["text_main"]))
            screen.blit(nm, (W//2-nm.get_width()//2, py+ph+16))
            ds = font_small.render(skin["desc"], True, (140,132,185)); screen.blit(ds, (W//2-ds.get_width()//2, py+ph+50))
        else:
            draw_gradient_rect(psf, (16,12,4), (24,18,6), (0,0,pw,ph))
            lx, ly = pw//2, ph//2-15
            pygame.draw.rect(psf, (140,115,0), (lx-22,ly,44,34), border_radius=6)
            pygame.draw.rect(psf, (200,160,0), (lx-22,ly,44,34), 2, border_radius=6)
            pygame.draw.arc(psf, (200,160,0), (lx-15,ly-26,30,34), 0, math.pi, 4)
            pygame.draw.circle(psf, (25,18,0), (lx,ly+14), 7)
            screen.blit(psf, (px,py)); pygame.draw.rect(screen, (100,80,0), (px,py,pw,ph), 2, border_radius=10)
            nm = font_big.render("LEGENDAR", True, (110,85,0)); screen.blit(nm, (W//2-nm.get_width()//2, py+ph+16))
            uh = font_small.render(skin["unlock_hint"], True, (150,120,45)); screen.blit(uh, (W//2-uh.get_width()//2, py+ph+50))
        # sageti laterale
        ay = py+ph//2
        if current_skin_idx > 0:
            al = font_big.render("<", True, (160,155,210)); screen.blit(al, (px-52,ay-al.get_height()//2))
        if current_skin_idx < len(SKIN_ORDER)-1:
            ar = font_big.render(">", True, (160,155,210)); screen.blit(ar, (px+pw+14,ay-ar.get_height()//2))
        # indicatori (puncte)
        ds0 = W//2-(len(SKIN_ORDER)*20)//2
        for i in range(len(SKIN_ORDER)):
            on = is_skin_unlocked(SKIN_ORDER[i]); sel = i == current_skin_idx
            col = ((200,200,255) if sel else (55,52,100)) if on else ((55,42,0) if sel else (28,20,0))
            pygame.draw.circle(screen, col, (ds0+i*20,py+ph+80), 6 if sel else 4)
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_LEFT and current_skin_idx > 0: current_skin_idx -= 1
                if ev.key == pygame.K_RIGHT and current_skin_idx < len(SKIN_ORDER)-1: current_skin_idx += 1
                if ev.key == pygame.K_RETURN and unlocked: return
                if ev.key == pygame.K_ESCAPE: return

class Button:
    def __init__(self, text, x, y, w, h, color, hover, font=None):
        self.text = text; self.rect = pygame.Rect(x,y,w,h); self.color = color; self.hover = hover; self.font = font or font_med
    def draw(self, surf, mp):
        c = self.hover if self.rect.collidepoint(mp) else self.color
        draw_gradient_rect(surf, tuple(min(255,v+20) for v in c), c, (self.rect.x,self.rect.y,self.rect.w,self.rect.h))
        pygame.draw.rect(surf, tuple(min(255,v+60) for v in c), self.rect, 1, border_radius=8)
        txt = self.font.render(self.text, True, WHITE)
        surf.blit(txt, (self.rect.centerx-txt.get_width()//2, self.rect.centery-txt.get_height()//2))
    def clicked(self, mp): return self.rect.collidepoint(mp)

def get_player_name():
    name = ""; clock = pygame.time.Clock(); t = 0.0; _init_bg_particles(40)
    btn = Button("START  >", W//2-110, 400, 220, 48, (50,110,50), (70,160,70))
    while True:
        t += clock.tick(30)/1000.0; mp = pygame.mouse.get_pos()
        draw_gradient_rect(screen, (8,6,20), (16,12,38), (0,0,W,H))
        _update_bg_particles(t and 0.03 or 0.03, [(220,50,50),(255,140,0),(255,255,255)])
        _draw_bg_particles(screen, [(220,50,50),(255,140,0),(255,255,255)])
        lf = _f(int(52*(1.0+0.04*math.sin(t*2))))
        t1 = lf.render("RAPID ", True, (220,50,50)); t2 = lf.render("FIRE", True, (255,140,0))
        tw = t1.get_width()+t2.get_width()
        screen.blit(t1, (W//2-tw//2,145)); screen.blit(t2, (W//2-tw//2+t1.get_width(),145))
        prompt = font_med.render("Introdu numele tau:", True, (160,155,210))
        screen.blit(prompt, (W//2-prompt.get_width()//2, 230))
        disp = name+("|" if int(t*2)%2==0 else " ")
        draw_glass_panel(screen, (W//2-165,262,330,44), color=(20,16,40), alpha=200, border_color=(100,80,180), radius=10)
        dt = font_med.render(disp, True, (80,220,80)); screen.blit(dt, (W//2-dt.get_width()//2, 272))
        btn.draw(screen, mp)
        hn = font_tiny.render("sau apasa ENTER", True, (80,75,115)); screen.blit(hn, (W//2-hn.get_width()//2, 458))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and btn.clicked(mp) and name: return name
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_RETURN and name: return name
                elif ev.key == pygame.K_BACKSPACE: name = name[:-1]
                elif len(name) < 20 and ev.unicode.isprintable(): name += ev.unicode

def show_menu(player_name):
    clock = pygame.time.Clock(); t = 0.0; _init_bg_particles(50)
    BW, BH = 270, 48; bx = W//2-BW//2
    defs = [("> Start Joc","play",(45,95,45),(65,145,65)), ("# Scoreboard","scores",(35,55,115),(55,85,165)),
            ("* Achievements","achievements",(75,55,25),(115,85,35)), ("= Statistici","stats",(25,65,85),(40,105,125)),
            ("~ Skinuri","skins",(72,45,110),(112,65,165)), ("X Iesire","exit",(95,28,28),(145,42,42))]
    buttons = [(Button(txt,bx,225+i*58,BW,BH,c,h), act) for i,(txt,act,c,h) in enumerate(defs)]
    while True:
        t += clock.tick(30)/1000.0; skin = get_skin(); mp = pygame.mouse.get_pos()
        draw_gradient_rect(screen, (8,6,20), (16,12,38), (0,0,W,H))
        _update_bg_particles(0.03, skin["particle_colors"]); _draw_bg_particles(screen, skin["particle_colors"])
        lf = _f(int(46*(1.0+0.03*math.sin(t*1.8))))
        t1 = lf.render("RAPID ", True, (220,50,50)); t2 = lf.render("FIRE", True, (255,140,0))
        tw = t1.get_width()+t2.get_width()
        screen.blit(t1, (W//2-tw//2,23)); screen.blit(t2, (W//2-tw//2+t1.get_width(),23))
        pn = font_med.render(f"Jucator:  {player_name}", True, safe_color3(skin["text_main"]))
        screen.blit(pn, (W//2-pn.get_width()//2, 78))
        for btn,_ in buttons: btn.draw(screen, mp)
        hint = font_tiny.render("taste  1 - 6  pentru navigare rapida", True, (65,60,95))
        screen.blit(hint, (W//2-hint.get_width()//2, 568))
        pygame.display.flip()
        for ev in _quit_events():
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for btn,act in buttons:
                    if btn.clicked(mp): 
                        if act == "exit": pygame.quit(); exit()
                        return act
            if ev.type == pygame.KEYDOWN:
                km = {pygame.K_1:"play",pygame.K_2:"scores",pygame.K_3:"achievements",pygame.K_4:"stats",pygame.K_5:"skins"}
                if ev.key in km: return km[ev.key]
                if ev.key == pygame.K_6: pygame.quit(); exit()

# ===== JOCUL PROPRIU-ZIS =====

def play_game(player_name, sounds):
    stats = load_stats(); best_before = stats["best_score"]; clock = pygame.time.Clock()
    level_idx = 0; total_score = 0; targets = []
    last_spawn = time.time(); level_start = time.time(); level_score = 0
    crosshair = (W//2, GAME_H//2); combo = 0; combo_flash = 0.0; prev_mult = 1
    bomb_flash = 0.0; BOMB_FLASH = 0.4; reached_max = False
    hits = misses = max_combo = bombs_hit = 0
    no_bomb = True; miss_this_level = False; new_ach = []
    active_pu = None; pu_timer = 0.0; time_scale = 1.0
    frenzy = False; frenzy_timer = 0.0; frenzy_done = False
    floats = []; particles = []; notif = NotificationQueue()
    last_pu_spawn = time.time(); paused = False
    _init_bg_particles(50)
    if get_skin().get("legendar"): _init_legend_stars()

    def check_achievements():
        newly = []
        def unlock(aid):
            ad = next((a for a in ACHIEVEMENTS if a["id"] == aid), None)
            if ad and unlock_achievement(stats, aid):
                newly.append(ad); notif.add(f"{ad['icon']}  {ad['name']}  deblocat!", GRADE_COLORS["S"]); play_sfx(sounds,"achievement")
        if stats["total_games"] >= 1: unlock("first_game")
        if max_combo >= 20: unlock("combo20")
        if not miss_this_level and level_idx == 0: unlock("no_miss_lvl1")
        if frenzy_done: unlock("first_frenzy")
        if set(stats.get("powerups_used",[])) >= {"freeze","slow","double"}: unlock("powerup_all")
        if total_score >= 200: unlock("score_200")
        if no_bomb and stats["total_games"] >= 1: unlock("no_bomb")
        if is_skin_unlocked("legendar"): unlock("legendar_skin")
        return newly

    def finish(quit_early=False):
        # Salveaza scor + statistici la finalul jocului
        nonlocal new_ach
        stats["total_games"] += 1; stats["total_hits"] += hits; stats["total_misses"] += misses
        stats["total_bombs_hit"] += bombs_hit; stats["max_combo"] = max(stats["max_combo"], max_combo)
        stats["best_score"] = max(stats["best_score"], total_score)
        if no_bomb and not quit_early: stats["no_bomb_games"] = stats.get("no_bomb_games",0)+1
        ach = [] if quit_early else check_achievements()
        save_stats(stats); save_score(player_name, total_score); play_sfx(sounds,"gameover")
        return total_score, (reached_max and not quit_early), hits, misses, max_combo, ach, best_before

    show_countdown()

    while True:
        dt_real = clock.tick(60)/1000.0; lvl = LEVELS[level_idx]; now = time.time()
        remaining = max(0, lvl["time_limit"]-(now-level_start)); skin = get_skin()

        # --- PAUZA ---
        if paused:
            draw_gradient_rect(screen, (8,6,18), (14,11,28), (0,0,W,H))
            draw_glass_panel(screen, (W//2-200,H//2-80,400,160), color=(20,16,40), alpha=220, border_color=(100,80,200), radius=14)
            pt = font_big.render("PAUZA", True, (200,200,255)); screen.blit(pt, (W//2-pt.get_width()//2,H//2-60))
            ph = font_small.render("P / ESC  --  continua          Q  --  paraseste", True, (120,115,165))
            screen.blit(ph, (W//2-ph.get_width()//2,H//2+10)); pygame.display.flip()
            for ev in _quit_events():
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_p, pygame.K_ESCAPE): paused = False
                    if ev.key == pygame.K_q: return finish(quit_early=True)
            continue

        dt = dt_real*time_scale
        # --- timere powerup / frenzy / flash ---
        if active_pu:
            pu_timer -= dt_real
            if pu_timer <= 0: active_pu = None; time_scale = 1.0
        if frenzy:
            frenzy_timer -= dt_real
            if frenzy_timer <= 0: frenzy = False
        combo_flash = max(0.0, combo_flash-dt_real); bomb_flash = max(0.0, bomb_flash-dt_real)

        # --- spawn obiecte ---
        spawn_interval = lvl["spawn_time"]*SPAWN_MULT*(0.4 if frenzy else 1.0)
        if now-last_spawn > spawn_interval:
            roll = random.random(); can_pu = (now-last_pu_spawn) > POWERUP_INTERVAL
            if roll < BOMB_CHANCE: targets.append(Bomb(lvl))
            elif roll < BOMB_CHANCE+POWERUP_CHANCE and can_pu: targets.append(PowerUp(lvl)); last_pu_spawn = now
            else: targets.append(Target(lvl))
            last_spawn = now

        # --- update entitati (freeze opreste doar tintele normale) ---
        targets = [t for t in targets if t.alive()]
        for t in targets:
            if active_pu == "freeze" and not t.is_bomb and not t.is_powerup: continue
            t.update(dt)
        for fx in floats: fx.update(dt_real)
        floats = [fx for fx in floats if fx.alive()]
        for p in particles: p.update(dt_real)
        particles = [p for p in particles if p.alive()]
        notif.update(dt_real)

        # --- input ---
        for ev in _quit_events():
            if ev.type == pygame.MOUSEMOTION: crosshair = ev.pos
            if ev.type == pygame.KEYDOWN and ev.key == pygame.K_p: paused = True
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                mx, my = ev.pos
                if my >= GAME_H: continue
                hit_something = False
                for t in targets[:]:
                    if not t.hit(mx, my): continue
                    if t.is_powerup:                                   # --- POWERUP ---
                        info = POWERUP_TYPES[t.ptype]; active_pu = t.ptype; pu_timer = info["duration"]
                        time_scale = 0.0 if t.ptype == "freeze" else (0.3 if t.ptype == "slow" else 1.0)
                        targets.remove(t); play_sfx(sounds,"powerup"); notif.add(f"{info['desc']}  ACTIVAT!", info["color"])
                        if t.ptype not in stats.get("powerups_used",[]): stats.setdefault("powerups_used",[]).append(t.ptype)
                        for _ in range(8): particles.append(HitParticle(mx,my,info["color"]))
                    elif t.is_bomb:                                    # --- BOMBA ---
                        pen = min(BOMB_PENALTY, total_score); total_score -= pen; level_score = max(0, level_score-pen)
                        combo = 0; prev_mult = 1; bomb_flash = BOMB_FLASH
                        targets.remove(t); play_sfx(sounds,"bomb"); bombs_hit += 1; no_bomb = False
                        floats.append(FloatText(mx,my,f"-{pen}",(220,50,50)))
                        for _ in range(12): particles.append(HitParticle(mx,my,(220,50,50)))
                    else:                                              # --- TINTA ---
                        combo += 1; combo_flash = 0.15; max_combo = max(max_combo, combo)
                        mult = get_combo_multiplier(combo)*(2 if active_pu == "double" else 1)
                        pts = t.n*mult; total_score += pts; level_score += pts; hits += 1; targets.remove(t)
                        if mult > prev_mult: play_sfx(sounds,"combo"); prev_mult = mult
                        else: play_sfx(sounds,"hit")
                        for _ in range(6): particles.append(HitParticle(mx,my,skin["particle_colors"][0]))
                        big = pts > t.n
                        floats.append(FloatText(mx,my,f"+{pts}",(255,210,0) if big else (80,230,80),big=big))
                        if combo >= FRENZY_COMBO_TRIGGER and not frenzy:   # declanseaza Frenzy
                            frenzy = True; frenzy_timer = FRENZY_DURATION; frenzy_done = True
                            stats["frenzy_count"] = stats.get("frenzy_count",0)+1
                            play_sfx(sounds,"frenzy"); notif.add("FRENZY ACTIVAT!  Spawn x2!", (255,120,0))
                    hit_something = True; break
                if not hit_something:                                  # click ratat
                    combo = 0; prev_mult = 1; play_sfx(sounds,"miss"); misses += 1; miss_this_level = True
                    floats.append(FloatText(mx,my,"X",(180,60,60)))

        # --- trecere nivel ---
        if level_score >= lvl["score_to_pass"] and level_idx < len(LEVELS)-1:
            level_idx += 1; level_start = time.time(); level_score = 0; targets.clear(); last_spawn = time.time()
            combo = 0; prev_mult = 1; miss_this_level = False; play_sfx(sounds,"levelup")
        if level_idx == len(LEVELS)-1: reached_max = True
        if remaining <= 0: return finish()

        # --- DESEN ---
        draw_background(screen, skin, frenzy=frenzy, dt=dt_real)
        if bomb_flash > 0:
            fs = pygame.Surface((W,GAME_H), pygame.SRCALPHA); fs.fill((220,0,0,int(140*(bomb_flash/BOMB_FLASH)))); screen.blit(fs,(0,0))
        if active_pu == "freeze":
            fz = pygame.Surface((W,GAME_H), pygame.SRCALPHA); fz.fill((80,180,255,14)); screen.blit(fz,(0,0))
            pygame.draw.rect(screen, (80,180,255), (0,0,W,GAME_H), 2)
        for t in targets: t.draw(screen)
        for p in particles: p.draw(screen)
        for fx in floats: fx.draw(screen)
        draw_crosshair(screen, skin, *crosshair, active_pu)
        draw_combo(screen, combo, combo_flash)
        draw_frenzy_hud(screen, frenzy_timer if frenzy else 0)
        draw_active_powerup(screen, active_pu, pu_timer)
        notif.draw(screen)
        draw_panel(screen, skin, frenzy=frenzy)

        # text panou
        time_col = (220,60,60) if remaining < 10 else safe_color3(skin["text_sub"])
        screen.blit(font_big.render(f"Scor:  {total_score}", True, safe_color3(skin["text_main"])), (18,GAME_H+10))
        s2 = font_med.render(f"Level  {level_idx+1} / 5", True, safe_color3(skin["text_sub"])); screen.blit(s2, (W//2-s2.get_width()//2,GAME_H+10))
        s3 = font_med.render(f"Timp:  {int(remaining)}s", True, time_col); screen.blit(s3, (W-s3.get_width()-18,GAME_H+10))
        screen.blit(font_small.render(f"Urmatorul nivel:  {level_score} / {lvl['score_to_pass']}   |   P = pauza", True, safe_color3(skin["text_dim"])), (18,GAME_H+52))
        bar_col = (255,120,0) if frenzy else safe_color3(skin["bar_fill"])
        draw_progress_bar(screen, (18,GAME_H+82,W-36,22), min(1.0,level_score/lvl["score_to_pass"]), bar_col, skin["bar_bg"], radius=6)
        if remaining < 10:
            ts = pygame.Surface((W,GAME_H), pygame.SRCALPHA)
            pygame.draw.rect(ts, (220,0,0,int(120+80*math.sin(time.time()*6))//4), (0,0,W,GAME_H), 3); screen.blit(ts,(0,0))
        pygame.display.flip()

# ===== MAIN =====

def main():
    sounds = init_sounds(); player = get_player_name(); _init_bg_particles(50)
    while True:
        action = show_menu(player)
        if action == "scores": show_scoreboard()
        elif action == "achievements": show_achievements()
        elif action == "stats": show_statistics()
        elif action == "skins": show_skin_select()
        elif action == "play":
            score, reached_max, hits, misses, max_combo, new_ach, best_before = play_game(player, sounds)
            newly = False
            if reached_max and not is_skin_unlocked("legendar"):     # deblocheaza skinul Legendar
                save_unlock("legendar"); newly = True
                ad = next((a for a in ACHIEVEMENTS if a["id"] == "legendar_skin"), None)
                if ad and ad not in new_ach: new_ach.append(ad)
            show_results_screen(score, hits, misses, max_combo, new_ach, best_before)
            if newly: show_unlock_screen(sounds)

if __name__ == "__main__":
    main()