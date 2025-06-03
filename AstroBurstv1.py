import pygame
import sys
from random import randint as r, choice, uniform as rand_uniform
from os.path import join
import cv2

# Initialize pygame
pygame.init()
pygame.mixer.init()

# --- Path Constants (Defined Early) ---
# Corrected paths assuming the script runs from a directory
# where 'Video', 'audio', 'images', 'font' are direct subdirectories.
VIDEO_BASE_PATH = 'Video'
AUDIO_BASE_PATH = 'audio'
IMAGE_BASE_PATH = 'images'
FONT_BASE_PATH = join('font', 'poppins')

GAME_MUSIC_PATH = join(AUDIO_BASE_PATH, 'Game-music.wav')
STORYBUILD_AUDIO_PATH = join(AUDIO_BASE_PATH, 'StoryBuild.wav')
START_MENU_MUSIC_PATH = join(AUDIO_BASE_PATH, 'StartScreen.wav')
LASER_SOUND_PATH = join(AUDIO_BASE_PATH, 'Laser_sound.wav')
CREDITS_MUSIC_PATH = join(AUDIO_BASE_PATH, 'CreditScreen.wav')

VIDEO_PATH_START = join(VIDEO_BASE_PATH, 'StartScreenMain.mp4')
VIDEO_PATH_INTRO_CLIP_1 = join(VIDEO_BASE_PATH, 'IntroClip.mp4')
VIDEO_PATH_INTRO_CLIP_2 = join(VIDEO_BASE_PATH, 'StoryBuild.mp4')
VIDEO_PATH_CREDITS = join(VIDEO_BASE_PATH, 'CreditScreen.mp4')
VIDEO_PATH_GAME_OVER = join(VIDEO_BASE_PATH, 'ExitScreenMain.mp4')

ICON_IMAGE_PATH = join(IMAGE_BASE_PATH, 'Meteor_1.png')


# Display setup
display_width, display_height = 1280, 720
screen = pygame.display.set_mode((display_width, display_height))
pygame.display.set_caption("AstroBurst")
try:
    game_icon = pygame.image.load(ICON_IMAGE_PATH)
    pygame.display.set_icon(game_icon)
    print(f"DEBUG: Game icon set to {ICON_IMAGE_PATH}")
except pygame.error as e:
    print(f"Error loading game icon '{ICON_IMAGE_PATH}': {e}. Using default icon.")
except FileNotFoundError:
    print(f"Game icon file not found: '{ICON_IMAGE_PATH}'. Using default icon.")


clock = pygame.time.Clock()
running = True

TIME_SCORE_RATE = 1

# --- Game Intro Animation Constants ---
INTRO_CLIP_2_DURATION = 5.0
GAME_INTRO_DURATION = 2.0
PRIMARY_TARGET_TEXT_EFFECT_DURATION = 2.5
game_intro_start_time = 0.0
intro_clip_2_start_time = 0.0
primary_target_text_effect_start_time = 0.0
PLAYER_NORMAL_START_Y = display_height - 100
PLAYER_ANIM_START_Y = display_height + 100

# --- Screen Shake Constants & Variables ---
SHAKE_INTENSITY = 6
SHAKE_DURATION_ON_HIT = 0.15
shake_timer = 0.0
current_shake_offset = (0, 0)


# --- Level System Constants & Variables ---
PRIMARY_TARGET_SCORE = 2000
LEVEL_DATA = [
    {'target': PRIMARY_TARGET_SCORE, 'is_credits_trigger': True, 'credits_video_path': VIDEO_PATH_CREDITS,
     'credits_music_path': CREDITS_MUSIC_PATH,
     'meteor_speed_multiplier': 1.0,  'meteor_spawn_rate_multiplier': 1.0}
]
MAX_LEVELS = len(LEVEL_DATA)

SPEED_INCREASE_INTERVAL = 500
PLAYER_SPEED_INCREMENT = 15
METEOR_BASE_SPEED_INCREMENT = 20
score_at_last_speed_increase = 0
current_meteor_base_speed_offset = 0

current_level = 1
target_score = LEVEL_DATA[0]['target']
current_level_meteor_speed_multiplier = LEVEL_DATA[0]['meteor_speed_multiplier']
current_level_meteor_spawn_rate_multiplier = LEVEL_DATA[0]['meteor_spawn_rate_multiplier']
BASE_METEOR_SPAWN_NORMAL_INTERVAL = 900
BASE_METEOR_SPAWN_FAST_INTERVAL = 1300

display_level_start_text_timer = 0.0
cap_credits_video = None

# --- Video Capture Objects - Initialize all to None ---
cap_start = None
cap_intro_clip_1 = None
cap_intro_clip_2 = None
cap_game_over = None

latest_intro_clip_1_pygame_surface = None
latest_intro_clip_2_pygame_surface = None


# --- Sprite groups ---
all_sprites = pygame.sprite.Group()
meteor_sprites = pygame.sprite.Group()
laser_sprites = pygame.sprite.Group()
player_group = pygame.sprite.GroupSingle()
tail_group = pygame.sprite.GroupSingle()

class Spaceship(pygame.sprite.Sprite):
    def __init__(self, groups, start_mode="normal"):
        super().__init__(groups)
        try:
            self.image_original = pygame.image.load(join(IMAGE_BASE_PATH, 'player.png')).convert_alpha()
        except pygame.error as e:
            print(f"Error loading player image: {e}. Using fallback surface.")
            self.image_original = pygame.Surface((50,40), pygame.SRCALPHA)
            self.image_original.fill((0,255,0))
        self.image = self.image_original

        self.normal_start_y = PLAYER_NORMAL_START_Y
        self.intro_anim_start_y = PLAYER_ANIM_START_Y
        self.is_in_intro_animation = False

        current_start_y = self.normal_start_y
        if start_mode == "intro_animation":
            current_start_y = self.intro_anim_start_y
            self.is_in_intro_animation = True

        self.rect = self.image.get_frect(center=(display_width / 2, current_start_y))
        self.direction = pygame.Vector2()
        self.base_speed = 300
        self.speed = self.base_speed
        self.mask = pygame.mask.from_surface(self.image)
        self.laser_active = False
        self.last_shot_time = 0
        self.laser_cooldown = 300

    def update(self, dt):
        global game_state, game_intro_start_time

        if self.is_in_intro_animation and game_state == "game_intro_animation":
            elapsed_intro_time = (pygame.time.get_ticks() / 1000.0) - game_intro_start_time
            if elapsed_intro_time < GAME_INTRO_DURATION:
                progress = min(1.0, elapsed_intro_time / GAME_INTRO_DURATION)
                self.rect.centery = self.intro_anim_start_y + (self.normal_start_y - self.intro_anim_start_y) * progress
                self.rect.centerx = display_width / 2
            else:
                self.rect.centery = self.normal_start_y
                self.rect.centerx = display_width / 2
                self.is_in_intro_animation = False
            return

        keys = pygame.key.get_pressed()
        self.direction.x = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
        self.direction.y = int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])

        if self.direction.magnitude() != 0:
            self.direction = self.direction.normalize()

        self.rect.center += self.direction * self.speed * dt
        self.rect.clamp_ip(screen.get_rect())

        current_time = pygame.time.get_ticks()
        if keys[pygame.K_SPACE]:
            if not self.laser_active and (current_time - self.last_shot_time > self.laser_cooldown):
                Laser(self.rect.midtop, (all_sprites, laser_sprites))
                if 'laser_sound' in globals() and laser_sound:
                    laser_sound.play()
                self.laser_active = True
                self.last_shot_time = current_time
        else:
            self.laser_active = False

class Laser(pygame.sprite.Sprite):
    def __init__(self, position, groups):
        super().__init__(groups)
        try:
            original_laser_image = pygame.image.load(join(IMAGE_BASE_PATH, 'laser.png')).convert_alpha()
            new_width = 50; new_height = 50
            self.image = pygame.transform.smoothscale(original_laser_image, (new_width, new_height))
        except pygame.error as e:
            print(f"Error loading laser image: {e}. Using fallback surface.")
            self.image = pygame.Surface((10,30), pygame.SRCALPHA); self.image.fill((255,0,0))
        
        self.rect = self.image.get_frect(midbottom=position)
        self.mask = pygame.mask.from_surface(self.image)
        self.speed = 700
    def update(self, dt): self.rect.y -= self.speed * dt; _ = self.kill() if self.rect.bottom < 0 else None

class Meteor(pygame.sprite.Sprite):
    def __init__(self, surf, position, scale_tuple, score_value, speed_multiplier, groups):
        super().__init__(groups)
        self.original_surface = surf
        self.image = pygame.transform.smoothscale(self.original_surface, scale_tuple)
        self.rect = self.image.get_frect(center=position)
        self.mask = pygame.mask.from_surface(self.image)
        self.direction = pygame.Vector2(rand_uniform(-0.5, 0.5), 1).normalize()
        self.base_speed = (r(150, 300) + current_meteor_base_speed_offset) * speed_multiplier
        self.current_speed = self.base_speed
        self.rotation_speed = r(20, 70); self.rotation = 0
        self.rotozoom_scale = self.rect.width / self.original_surface.get_width() if self.original_surface.get_width() > 0 else 1.0
        self.score_value = score_value

    def update(self, dt):
        self.rect.center += self.direction * self.current_speed * dt
        self.rotation += self.rotation_speed * dt
        old_center = self.rect.center
        self.image = pygame.transform.rotozoom(self.original_surface, self.rotation, self.rotozoom_scale)
        self.rect = self.image.get_frect(center=old_center)
        self.mask = pygame.mask.from_surface(self.image)
        if self.rect.top > display_height + 50 or self.rect.right < -50 or self.rect.left > display_width + 50:
            self.kill()

class LoopingObject(pygame.sprite.Sprite):
    def __init__(self, surf, new_top_y_on_reset, pos, speed, groups):
        super().__init__(groups); self.image = surf; self.rect = self.image.get_frect(topleft=pos)
        self.base_speed = speed
        self.current_speed = speed
        self.reset_y = new_top_y_on_reset
    def update(self, dt):
        self.rect.y += self.current_speed * dt
        if self.rect.top >= display_height: self.rect.top = self.reset_y

class AnimatedExplosion(pygame.sprite.Sprite):
    def __init__(self, frames, pos, groups):
        super().__init__(groups); self.frames = frames; self.frame_index = 0
        if not self.frames: self.image = pygame.Surface((1,1)); self.kill(); return
        self.image = self.frames[self.frame_index]; self.rect = self.image.get_frect(center=pos)
        self.animation_speed = 25
    def update(self, dt):
        if not self.frames: self.kill(); return
        self.frame_index += self.animation_speed * dt
        self.image = self.frames[int(self.frame_index)] if self.frame_index < len(self.frames) else self.kill()

class Spaceshiptail(pygame.sprite.Sprite):
    def __init__(self, frames, player_ref, groups):
        super().__init__(groups); self.player = player_ref; self.frames = frames; self.frame_index = 0
        if not self.frames: self.image = pygame.Surface((1,1)); self.kill(); return
        self.image = self.frames[self.frame_index]
        self.offset_y = self.image.get_height() / 2 - 10
        self.rect = self.image.get_frect(midtop=(self.player.rect.centerx, self.player.rect.bottom - self.offset_y))
        self.animation_speed = 30
    def update(self, dt):
        if not self.player.alive() or not self.frames: self.kill(); return
        self.rect.midtop = (self.player.rect.centerx, self.player.rect.bottom - self.offset_y + 5)
        self.frame_index += self.animation_speed * dt
        self.image = self.frames[int(self.frame_index) % len(self.frames)]

class ScorePopup(pygame.sprite.Sprite):
    def __init__(self, text, position, font, color, duration_ms, upward_speed, groups):
        super().__init__(groups); self.font = font
        self.image_original = self.font.render(text, True, color); self.image = self.image_original.copy()
        self.rect = self.image.get_rect(center=position)
        self.creation_time = pygame.time.get_ticks(); self.duration_ms = duration_ms
        self.upward_speed = upward_speed; self.initial_alpha = 255; self.image.set_alpha(self.initial_alpha)
    def update(self, dt):
        elapsed_time = pygame.time.get_ticks() - self.creation_time
        if elapsed_time >= self.duration_ms: self.kill(); return
        self.rect.y -= self.upward_speed * dt
        if elapsed_time > self.duration_ms / 2:
            alpha_ratio = 1.0 - ((elapsed_time - self.duration_ms/2) / (self.duration_ms/2))
            self.image.set_alpha(max(0, int(self.initial_alpha * alpha_ratio)))

# --- Global Score & Level Variables ---
current_score = 0

# --- Collision & Game Logic ---
def check_collisions_and_level_up():
    global game_state, current_score, shake_timer, target_score, current_level, cap_credits_video
    
    collisions_laser_meteor = pygame.sprite.groupcollide(laser_sprites, meteor_sprites, True, True, pygame.sprite.collide_mask)
    for laser, meteors_hit in collisions_laser_meteor.items():
        for meteor in meteors_hit:
            current_score += meteor.score_value
            shake_timer = SHAKE_DURATION_ON_HIT
            if score_popup_font:
                ScorePopup(f"+{meteor.score_value}", meteor.rect.center, score_popup_font, (255, 223, 0), 1000, 70, all_sprites)
            if explosion_frames_resized:
                AnimatedExplosion(explosion_frames_resized, meteor.rect.center, all_sprites)

    if player_group.sprite and player_group.sprite.alive():
        collided_meteor = pygame.sprite.spritecollideany(player_group.sprite, meteor_sprites, pygame.sprite.collide_mask)
        if collided_meteor:
            if explosion_frames_resized:
                AnimatedExplosion(explosion_frames_resized, player_group.sprite.rect.center, all_sprites)
            player_group.sprite.kill()
            if tail_group.sprite: tail_group.sprite.kill()
            
            if pygame.mixer.music.get_busy(): 
                pygame.mixer.music.stop()
                print("DEBUG: Main game music stopped (player collision game over).")
            
            game_state = "game_over" 

            pygame.time.set_timer(METEOR_SPAWN_NORMAL, 0)
            pygame.time.set_timer(METEOR_SPAWN_FAST, 0)
            return

    if current_score >= target_score and game_state == "game": 
        print(f"Primary Target of {target_score} reached! Score: {current_score}")
        if pygame.mixer.music.get_busy(): 
            pygame.mixer.music.stop()
            print("DEBUG: Main game music stopped (primary target reached for credits).")

        pygame.time.set_timer(METEOR_SPAWN_NORMAL, 0) 
        pygame.time.set_timer(METEOR_SPAWN_FAST, 0)
        for m in meteor_sprites: m.kill() 
        for l in laser_sprites: l.kill()
        
        level_index = current_level - 1 
        if LEVEL_DATA[level_index].get('is_credits_trigger', False):
            credits_video_path = LEVEL_DATA[level_index].get('credits_video_path')
            credits_music_path = LEVEL_DATA[level_index].get('credits_music_path')
            
            if credits_video_path:
                print(f"DEBUG: Triggering credits video: {credits_video_path}")
                game_state = "playing_credits_video" 
                try:
                    if cap_credits_video: cap_credits_video.release()
                    cap_credits_video = cv2.VideoCapture(credits_video_path)
                    if not cap_credits_video or not cap_credits_video.isOpened():
                        print(f"Error opening credits video: {credits_video_path}. Returning to start menu.")
                        cap_credits_video = None
                        game_state = "start_menu" 
                        if start_menu_music: start_menu_music.play(loops=0)
                    elif credits_music_path : 
                        try:
                            pygame.mixer.music.load(credits_music_path) 
                            pygame.mixer.music.set_volume(0.5) 
                            pygame.mixer.music.play(loops=-1) 
                            print(f"DEBUG: Playing credits music: {credits_music_path}")
                        except pygame.error as e_music:
                            print(f"Error loading/playing credits music {credits_music_path}: {e_music}")
                except Exception as e:
                    print(f"Exception loading credits video: {e}")
                    if cap_credits_video: cap_credits_video.release()
                    cap_credits_video = None
                    if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
                    game_state = "start_menu"
                    if start_menu_music: start_menu_music.play(loops=0)
            else: 
                print("DEBUG: Credits video path not defined. Returning to start menu.")
                game_state = "start_menu"
                if start_menu_music: start_menu_music.play(loops=0)
        # else: # No more levels after primary target + credits
        #     game_state = "start_menu"
        #     if start_menu_music: start_menu_music.play(loops=0)
            
    global score_at_last_speed_increase, current_meteor_base_speed_offset
    if game_state == "game" and current_score >= score_at_last_speed_increase + SPEED_INCREASE_INTERVAL:
        score_at_last_speed_increase += SPEED_INCREASE_INTERVAL 
        if player and player.alive(): 
            player.speed += PLAYER_SPEED_INCREMENT
            print(f"DEBUG: Player speed increased to {player.speed} at score {current_score}")
        current_meteor_base_speed_offset += METEOR_BASE_SPEED_INCREMENT
        print(f"DEBUG: Meteor base speed offset increased to {current_meteor_base_speed_offset} at score {current_score}")

# --- UI Display Functions ---
score_font = None; score_popup_font = None; placeholder_font = None
primary_target_font_main = None; primary_target_font_score_val = None

def display_score(surface_to_draw_on):
    if score_font and (game_state == "game" or game_state == "game_intro_animation" or game_state == "display_primary_target_text"):
        text_surface = score_font.render(f"Score: {int(current_score)}", True, (240, 240, 240))
        surface_to_draw_on.blit(text_surface, text_surface.get_frect(midtop=(display_width / 2, 10)))

def display_primary_target_text_effect(surface_to_draw_on): 
    global primary_target_text_effect_start_time, target_score, current_pygame_time_sec
    elapsed_effect_time = current_pygame_time_sec - primary_target_text_effect_start_time
    progress = min(1.0, elapsed_effect_time / PRIMARY_TARGET_TEXT_EFFECT_DURATION)
    
    alpha = int(pygame.math.smoothstep(0, 255, progress)) 

    if primary_target_font_main and primary_target_font_score_val:
        text1_str = "Primary Target"
        text2_str = str(target_score) 

        text1_surf = primary_target_font_main.render(text1_str, True, (255, 255, 255)) 
        text1_surf.set_alpha(alpha)
        
        scale_factor = 0.1 + 0.9 * progress 
        text2_color = (255, 255, 255) 
        
        surface_to_draw_on.fill((0,0,0)) 

        if scale_factor > 0.01 : 
            try:
                temp_score_font_size = int(primary_target_font_score_val.get_height() * scale_factor)
                if temp_score_font_size < 1: temp_score_font_size = 1
                
                scaled_font = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-ExtraLight.ttf'), temp_score_font_size)
                text2_surf_scaled = scaled_font.render(text2_str, True, text2_color)
                text2_surf_scaled.set_alpha(alpha)

                if progress < 0.8 : 
                    num_blurs = 3
                    blur_offset_range = 15 * (1.0 - progress) 
                    for _ in range(num_blurs):
                        blur_alpha = int(alpha * 0.15) 
                        text2_surf_scaled.set_alpha(blur_alpha)
                        offset_x = rand_uniform(-blur_offset_range, blur_offset_range)
                        offset_y = rand_uniform(-blur_offset_range, blur_offset_range)
                        surface_to_draw_on.blit(text2_surf_scaled, text2_surf_scaled.get_rect(center=(display_width / 2 + offset_x, display_height / 2 + 40 + offset_y)))
                
                text2_surf_scaled.set_alpha(alpha) 
                surface_to_draw_on.blit(text2_surf_scaled, text2_surf_scaled.get_rect(center=(display_width / 2, display_height / 2 + 40)))
            except pygame.error as font_error: 
                print(f"Font scaling error for primary target: {font_error}")
                unscaled_font_to_use = score_font if score_font else placeholder_font 
                text2_surf_unscaled = unscaled_font_to_use.render(text2_str, True, text2_color)
                text2_surf_unscaled.set_alpha(alpha)
                surface_to_draw_on.blit(text2_surf_unscaled, text2_surf_unscaled.get_rect(center=(display_width/2, display_height/2 + 40)))
        
        surface_to_draw_on.blit(text1_surf, text1_surf.get_rect(center=(display_width / 2, display_height / 2 - 50)))

# --- Game State & Video Assets ---
game_state = "start_menu"
start_menu_image_surf = pygame.image.load(join(IMAGE_BASE_PATH, 'StartScreen.png')).convert()
start_menu_image_surf = pygame.transform.scale(start_menu_image_surf, (display_width, display_height))
start_menu_rect = start_menu_image_surf.get_rect(center=(display_width // 2, display_height // 2))
start_menu_music = None 
try:
    start_menu_music = pygame.mixer.Sound(START_MENU_MUSIC_PATH)
except pygame.error as e: print(f"Error loading start menu music: {e}")

story_build_sound = None
try:
    story_build_sound = pygame.mixer.Sound(STORYBUILD_AUDIO_PATH)
    story_build_sound.set_volume(0.5) 
except pygame.error as e: print(f"Error loading StoryBuild sound ({STORYBUILD_AUDIO_PATH}): {e}")


cap_start = None
try:
    cap_start_temp = cv2.VideoCapture(VIDEO_PATH_START)
    if cap_start_temp and cap_start_temp.isOpened(): cap_start = cap_start_temp
    else:
        if cap_start_temp: cap_start_temp.release()
        print(f"Warning: Could not open start video: {VIDEO_PATH_START}"); cap_start = None
except Exception as e: print(f"Exception initializing start video: {e}"); cap_start = None

cap_intro_clip_1 = None; latest_intro_clip_1_pygame_surface = None
cap_intro_clip_2 = None; latest_intro_clip_2_pygame_surface = None
cap_game_over = None
try:
    cap_game_over_temp = cv2.VideoCapture(VIDEO_PATH_GAME_OVER)
    if cap_game_over_temp and cap_game_over_temp.isOpened(): cap_game_over = cap_game_over_temp
    else:
        if cap_game_over_temp: cap_game_over_temp.release()
        print(f"Warning: Could not open game over video: {VIDEO_PATH_GAME_OVER}"); cap_game_over = None
except Exception as e: print(f"Exception initializing game over video: {e}"); cap_game_over = None

# --- Video Frame Drawing Utility ---
def draw_video_frame_or_fallback(cap_obj, fallback_surf=None, fallback_rect=None, store_surface_global_var_name=None, loop=False):
    frame_drawn, video_ended = False, True; current_surf = None
    if cap_obj and cap_obj.isOpened():
        ret, frame = cap_obj.read()
        if not ret and loop: cap_obj.set(cv2.CAP_PROP_POS_FRAMES, 0); ret,frame = cap_obj.read()
        if ret:
            video_ended = False
            try:
                frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                current_surf = pygame.surfarray.make_surface(cv2.resize(frame,(display_width,display_height)).swapaxes(0,1))
                screen.blit(current_surf,(0,0)); frame_drawn = True
            except Exception as e: print(f"Frame error in draw_video: {e}"); current_surf = None
    if not frame_drawn:
        if fallback_surf and fallback_rect: screen.blit(fallback_surf,fallback_rect)
        else: screen.fill((5,5,5))
    if store_surface_global_var_name: globals()[store_surface_global_var_name] = current_surf
    return not video_ended

# --- Load Assets ---
try:
    score_font = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-ExtraLight.ttf'), 50)
    primary_target_font_main = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-ExtraLight.ttf'), 70) 
    primary_target_font_score_val = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-ExtraLight.ttf'), 90) 
    score_popup_font = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-Thin.ttf'), 28)
    placeholder_font = pygame.font.Font(join(FONT_BASE_PATH, 'Poppins-Regular.ttf'), 40) 
    # win_font removed from here
except pygame.error as e: print(f"Font loading error: {e}"); pygame.quit(); sys.exit()

try: background = pygame.image.load(join(IMAGE_BASE_PATH, 'Background.png')).convert()
except pygame.error as e: print(f"Background load error: {e}"); background = None

music_loaded_for_main_game = False 
try:
    pygame.mixer.music.load(GAME_MUSIC_PATH)
    pygame.mixer.music.set_volume(0.2) 
    music_loaded_for_main_game = True
    print(f"DEBUG: Game music {GAME_MUSIC_PATH} loaded into mixer.music channel.")
except pygame.error as e:
    print(f"Error loading game music ({GAME_MUSIC_PATH}) with pygame.mixer.music: {e}")
    music_loaded_for_main_game = False

laser_sound = None; credits_music = None
try: 
    laser_sound=pygame.mixer.Sound(LASER_SOUND_PATH)
    laser_sound.set_volume(0.15)
except pygame.error as e: print(f"Error loading laser sound: {e}")
try:
    credits_music = pygame.mixer.Sound(CREDITS_MUSIC_PATH) 
    credits_music.set_volume(0.5) 
except pygame.error as e: print(f"Error loading {CREDITS_MUSIC_PATH}: {e}")


if start_menu_music: start_menu_music.set_volume(0.3)

explosion_frames_resized=[]; meteor_surfaces=[]; back_stream_frames=[]
try:
    for i in range(8): explosion_frames_resized.append(pygame.transform.smoothscale(pygame.image.load(join(IMAGE_BASE_PATH,'Explosion_frames',f'{i}.png')).convert_alpha(),(90,90)))
    for i in range(1,4): meteor_surfaces.append(pygame.image.load(join(IMAGE_BASE_PATH,f'Meteor_{i}.png')).convert_alpha())
    for i in range(1,4): back_stream_frames.append(pygame.transform.smoothscale(pygame.image.load(join(IMAGE_BASE_PATH,'Spaceship_trail',f'{i}.png')).convert_alpha(),(30,50)))
except pygame.error as e: print(f"Error loading game sprites: {e}")
planet_sprites_info=[(join(IMAGE_BASE_PATH,f'Planet_{i}.png'),pos,spd) for i,pos,spd in [(1,(100,-400),40),(2,(display_width-300,-900),35),(3,(display_width/2,-1500),50)]]
try: stars_surface = pygame.image.load(join(IMAGE_BASE_PATH,'Stars.png')).convert_alpha()
except pygame.error as e: print(f"Error loading stars: {e}"); stars_surface = None

# --- Custom Events ---
METEOR_SPAWN_NORMAL=pygame.USEREVENT+1; METEOR_SPAWN_FAST=pygame.USEREVENT+2

# --- Game Control Functions ---
def start_full_gameplay_systems():
    global music_loaded_for_main_game
    global current_level_meteor_spawn_rate_multiplier
    
    print("DEBUG: start_full_gameplay_systems called")
    
    level_idx = current_level - 1
    current_spawn_mult = LEVEL_DATA[level_idx]['meteor_spawn_rate_multiplier']
    
    normal_spawn_interval = int(BASE_METEOR_SPAWN_NORMAL_INTERVAL * current_spawn_mult)
    fast_spawn_interval = int(BASE_METEOR_SPAWN_FAST_INTERVAL * current_spawn_mult)

    pygame.time.set_timer(METEOR_SPAWN_NORMAL, normal_spawn_interval)
    pygame.time.set_timer(METEOR_SPAWN_FAST, fast_spawn_interval)
    print(f"DEBUG: Level {current_level} - Meteor N spawn: {normal_spawn_interval}ms, F spawn: {fast_spawn_interval}ms")
    
    if music_loaded_for_main_game: 
        pygame.mixer.music.play(loops=-1)
        print("Game music started via mixer.music.")
    else:
        print("DEBUG: Main game music was not loaded, cannot play.")
    print("Full gameplay systems started.")

def setup_game(mode="normal_start"):
    global player,player_tail,current_score,all_sprites,meteor_sprites,laser_sprites,player_group,tail_group
    global current_level, target_score, current_level_meteor_speed_multiplier, current_level_meteor_spawn_rate_multiplier
    global score_at_last_speed_increase, current_meteor_base_speed_offset
    
    print(f"--- Setting up game, mode: {mode} ---")
    current_score = 0 
    score_at_last_speed_increase = 0 
    current_meteor_base_speed_offset = 0 
    
    if mode == "normal_start" and game_state != "game": 
        current_level = 1
    elif mode == "intro_animation_setup":
        current_level = 1 
    
    level_idx = current_level - 1 
    target_score = LEVEL_DATA[level_idx]['target']
    current_level_meteor_speed_multiplier = LEVEL_DATA[level_idx]['meteor_speed_multiplier']
    current_level_meteor_spawn_rate_multiplier = LEVEL_DATA[level_idx]['meteor_spawn_rate_multiplier']

    all_sprites.empty();meteor_sprites.empty();laser_sprites.empty();player_group.empty();tail_group.empty()
    player_start_mode = "intro_animation" if mode=="intro_animation_setup" else "normal"
    player_instance=Spaceship(player_group,start_mode=player_start_mode)
    globals()['player'] = player_instance 
    all_sprites.add(player_instance)

    if player: 
        player.speed = player.base_speed 

    if back_stream_frames:player_tail=Spaceshiptail(back_stream_frames,player,tail_group);all_sprites.add(player_tail)
    else: player_tail=None
    if stars_surface:
        star_w,star_h=stars_surface.get_width(),stars_surface.get_height()
        if star_w>0 and star_h>0:
            for i in range((display_width+star_w-1)//star_w):x=i*star_w;LoopingObject(stars_surface,-star_h,(x,0),20,all_sprites);LoopingObject(stars_surface,-star_h,(x,-star_h),20,all_sprites)
    for img_path,pos,speed in planet_sprites_info:
        try: surf=pygame.image.load(img_path).convert_alpha();LoopingObject(surf,-surf.get_height(),pos,speed,all_sprites)
        except pygame.error as e:print(f"Planet load error {img_path}: {e}")
    print(f"--- Game setup complete for mode: {mode} (Level: {current_level}, Target: {target_score}) ---")


# --- Main Game Loop ---
if game_state=="start_menu" and start_menu_music:
    start_menu_music.play(loops=0) 

game_render_surface = pygame.Surface((display_width,display_height))

while running:
    dt = clock.tick(60)/1000
    current_pygame_time_sec = pygame.time.get_ticks() / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT: running=False
        if game_state == "start_menu":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                if start_menu_music:start_menu_music.stop()
                if cap_start:cap_start.set(cv2.CAP_PROP_POS_FRAMES,0)
                try: 
                    cap_intro_clip_1=cv2.VideoCapture(VIDEO_PATH_INTRO_CLIP_1)
                    if not cap_intro_clip_1 or not cap_intro_clip_1.isOpened():
                        print(f"Error opening intro_clip_1. Skipping to intro_clip_2.")
                        cap_intro_clip_1=None;latest_intro_clip_1_pygame_surface=None;
                        intro_clip_2_start_time=current_pygame_time_sec;game_state="intro_clip_2";
                        if story_build_sound: story_build_sound.play() 
                        try: cap_intro_clip_2=cv2.VideoCapture(VIDEO_PATH_INTRO_CLIP_2)
                        except Exception as e_ic2: print(f"Err intro2 fallback: {e_ic2}"); cap_intro_clip_2=None
                        if cap_intro_clip_2 and not cap_intro_clip_2.isOpened(): cap_intro_clip_2=None
                    else: game_state="intro_clip_1" 
                except Exception as e_ic1:
                    print(f"Ex loading intro1: {e_ic1}. Skipping to intro_clip_2.")
                    cap_intro_clip_1=None;latest_intro_clip_1_pygame_surface=None
                    intro_clip_2_start_time=current_pygame_time_sec;game_state="intro_clip_2"
                    if story_build_sound: story_build_sound.play()
                    try: 
                        cap_intro_clip_2=cv2.VideoCapture(VIDEO_PATH_INTRO_CLIP_2)
                        if cap_intro_clip_2 and not cap_intro_clip_2.isOpened(): cap_intro_clip_2=None
                    except Exception as e_ic2: print(f"Err intro2 ex fallback: {e_ic2}"); cap_intro_clip_2=None
        
        elif game_state == "display_primary_target_text":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE: 
                print("DEBUG: Skipping Primary Target text effect, going to game_intro_animation.")
                # Story build sound should stop if clip 2 was playing and we skip this text effect state
                if story_build_sound and story_build_sound.get_num_channels() > 0 : story_build_sound.stop() 
                setup_game(mode="intro_animation_setup")
                game_intro_start_time=current_pygame_time_sec
                game_state="game_intro_animation"
        
        elif game_state=="game_over":
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    game_state="start_menu"
                    if start_menu_music and start_menu_music.get_num_channels() > 0 : start_menu_music.stop() 
                    if start_menu_music: start_menu_music.play(loops=0) 
                    if story_build_sound and story_build_sound.get_num_channels() > 0: story_build_sound.stop() 
                    for cap_obj in [cap_game_over, cap_intro_clip_1,cap_intro_clip_2,cap_credits_video]:
                        if cap_obj: cap_obj.release()
                    cap_intro_clip_1=None;cap_intro_clip_2=None;cap_credits_video=None; cap_game_over=None 
                elif event.key == pygame.K_RETURN:
                    # No music should be playing on game_over screen now.
                    setup_game(mode="normal_start");game_state="game";start_full_gameplay_systems()
        
        elif game_state == "playing_credits_video": 
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                print("DEBUG: ESC pressed during credits video. Transitioning to start menu.")
                if cap_credits_video: cap_credits_video.release(); cap_credits_video = None
                if pygame.mixer.music.get_busy(): pygame.mixer.music.stop() # Stop credits music
                game_state = "start_menu" 
                if start_menu_music: start_menu_music.play(loops=0)
        
        # game_won state effectively removed

        if game_state=="game":
            if event.type==METEOR_SPAWN_NORMAL:
                if meteor_surfaces:
                    x,y=r(50,display_width-50),r(-250,-80);sw=r(70,110)
                    min_h,max_h=int(sw*0.8),int(sw*1.2);sh=r(min_h,max_h) if min_h<=max_h else min_h
                    Meteor(choice(meteor_surfaces),(x,y),(sw,sh),10, current_level_meteor_speed_multiplier, (all_sprites,meteor_sprites))
            elif event.type==METEOR_SPAWN_FAST:
                if meteor_surfaces:
                    x,y=r(50,display_width-50),r(-250,-80);sw=r(50,90)
                    min_h,max_h=int(sw*0.8),int(sw*1.2);sh=r(min_h,max_h) if min_h<=max_h else min_h
                    m=Meteor(choice(meteor_surfaces),(x,y),(sw,sh),20, current_level_meteor_speed_multiplier, (all_sprites,meteor_sprites))
                    m.base_speed*=1.25; m.current_speed=m.base_speed

    # Game State Logic Updates
    current_shake_offset = (0,0)

    if game_state=="intro_clip_1":
        if not draw_video_frame_or_fallback(cap_intro_clip_1,None,None,'latest_intro_clip_1_pygame_surface'):
            if cap_intro_clip_1:cap_intro_clip_1.release();cap_intro_clip_1=None
            latest_intro_clip_1_pygame_surface=None
            intro_clip_2_start_time=current_pygame_time_sec
            game_state="intro_clip_2" 
            if story_build_sound: story_build_sound.play() 
            try:
                if not cap_intro_clip_2 or not cap_intro_clip_2.isOpened():cap_intro_clip_2=cv2.VideoCapture(VIDEO_PATH_INTRO_CLIP_2)
                if cap_intro_clip_2 and not cap_intro_clip_2.isOpened():cap_intro_clip_2=None
            except Exception as e:print(f"Error loading intro2 video: {e}");cap_intro_clip_2=None
    elif game_state=="intro_clip_2":
        elapsed_clip_2_time=current_pygame_time_sec-intro_clip_2_start_time;clip_2_ended=False
        if cap_intro_clip_2 and cap_intro_clip_2.isOpened():
            if not draw_video_frame_or_fallback(cap_intro_clip_2,None,None,'latest_intro_clip_2_pygame_surface'):clip_2_ended=True
        else:
            screen.fill((0,0,0))
            if placeholder_font:text_surf=placeholder_font.render("Story Build Clip Playing...",True,(200,200,200));screen.blit(text_surf,text_surf.get_rect(center=(display_width/2,display_height/2)))
        
        story_build_channel_busy = False
        if story_build_sound:
            for i in range(pygame.mixer.get_num_channels()):
                channel = pygame.mixer.Channel(i)
                if channel.get_sound() == story_build_sound and channel.get_busy():
                    story_build_channel_busy = True; break
        
        if (elapsed_clip_2_time>=INTRO_CLIP_2_DURATION or clip_2_ended) and not story_build_channel_busy :
            if story_build_sound: story_build_sound.stop() 
            if cap_intro_clip_2:cap_intro_clip_2.release();cap_intro_clip_2=None
            latest_intro_clip_2_pygame_surface=None
            primary_target_text_effect_start_time = current_pygame_time_sec
            game_state = "display_primary_target_text" 
            print("DEBUG: intro_clip_2 finished, transitioning to display_primary_target_text")

    elif game_state == "display_primary_target_text":
        elapsed_effect_time = current_pygame_time_sec - primary_target_text_effect_start_time
        if elapsed_effect_time >= PRIMARY_TARGET_TEXT_EFFECT_DURATION:
            print("DEBUG: Primary Target text effect finished, transitioning to game_intro_animation.")
            setup_game(mode="intro_animation_setup")
            game_intro_start_time=current_pygame_time_sec
            game_state="game_intro_animation"
            
    elif game_state=="game_intro_animation":
        all_sprites.update(dt)
        if current_pygame_time_sec-game_intro_start_time>=GAME_INTRO_DURATION:
            if player:player.is_in_intro_animation=False
            print("DEBUG: Transitioning from game_intro_animation to game state...")
            game_state="game";start_full_gameplay_systems()
    elif game_state=="game":
        current_score+=TIME_SCORE_RATE*dt
        if display_level_start_text_timer>0:display_level_start_text_timer-=dt # For Primary Target... text
                
        if shake_timer > 0:
            shake_timer -= dt
            current_shake_offset = (r(-SHAKE_INTENSITY, SHAKE_INTENSITY), r(-SHAKE_INTENSITY, SHAKE_INTENSITY)) if shake_timer > 0 else (0,0)
        
        all_sprites.update(dt)
        check_collisions_and_level_up()

    elif game_state == "playing_credits_video": 
        if not draw_video_frame_or_fallback(cap_credits_video, None, None, loop=True): 
            print("DEBUG: Credits video non-looping end OR error. Transitioning to start menu.")
            if cap_credits_video: cap_credits_video.release(); cap_credits_video = None
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop() 
            game_state = "start_menu" 
            if start_menu_music: start_menu_music.play(loops=0)
            
    elif game_state == "game_won": # No longer directly used, game ends after credits.
        print("DEBUG: In game_won state (should be rare). Transitioning to start menu.")
        game_state = "start_menu" 
        if start_menu_music: start_menu_music.play(loops=0)


    # --- Drawing Section ---
    game_render_surface.fill((0,0,0,0));game_render_surface.set_colorkey((0,0,0))

    if game_state=="start_menu":draw_video_frame_or_fallback(cap_start,start_menu_image_surf,start_menu_rect,loop=True)
    elif game_state == "display_primary_target_text":
        screen.fill((0,0,0)) 
        display_primary_target_text_effect(screen) 
    elif game_state=="intro_clip_1": _ = screen.fill((10,0,0)) if not latest_intro_clip_1_pygame_surface else None
    elif game_state=="intro_clip_2":
        if not(cap_intro_clip_2 and cap_intro_clip_2.isOpened()) and not latest_intro_clip_2_pygame_surface:pass
        elif latest_intro_clip_2_pygame_surface:pass
        else:screen.fill((0,10,0))
    elif game_state=="game_intro_animation" or game_state=="game":
        _ = game_render_surface.blit(background,(0,0)) if background else game_render_surface.fill((0,0,10))
        all_sprites.draw(game_render_surface)
        if 'player_tail' in globals() and player_tail and player_tail.alive():game_render_surface.blit(player_tail.image,player_tail.rect)
        if 'player' in globals() and player and player.alive():game_render_surface.blit(player.image,player.rect)
        if game_state=="game":
            display_score(game_render_surface)
            # "Primary Target" text now handled by display_primary_target_text state, so no other level start message needed for level 1
        screen.blit(game_render_surface,current_shake_offset)
    elif game_state=="playing_credits_video": 
        if not cap_credits_video or not cap_credits_video.isOpened(): 
            screen.fill((10,10,30)) 
            if placeholder_font:
                text_surf = placeholder_font.render("Playing Credits...",True,(200,200,255))
                screen.blit(text_surf, text_surf.get_rect(center=(display_width/2, display_height/2)))
    elif game_state == "game_won": # This state is no longer drawn as game goes to menu after credits.
        pass 
    elif game_state=="game_over":
        # Screen should be silent for game_over video display
        draw_video_frame_or_fallback(cap_game_over,None,None,loop=True) 
    pygame.display.flip()

# --- Release Resources ---
for cap_obj in [cap_start,cap_intro_clip_1,cap_intro_clip_2,cap_game_over,cap_credits_video]:
    if cap_obj: cap_obj.release()
pygame.mixer.quit()
pygame.quit()
sys.exit()