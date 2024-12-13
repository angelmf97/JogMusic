import tkinter as tk
from tkinter import filedialog
import threading
import queue
import librosa
import sounddevice as sd
import numpy as np
import cadence_inference
import bluetooth_receive
import time

class RealTimeAudioPlayer:
    def __init__(self, root, cadence_queue, bluetooth_queue):
        print(sd.query_devices())
        sd.default.device = 6
        self.root = root

        self.cadence_queue = cadence_queue
        self.bluetooth_queue = bluetooth_queue
        self.root.title("Real-Time Audio Speed Control")

        # UI Elements
        self.load_button = tk.Button(root, text="Load Audio", command=self.load_audio)
        self.load_button.pack(pady=10)

        self.play_button = tk.Button(root, text="Play", state=tk.DISABLED, command=self.play_audio)
        self.play_button.pack(pady=10)

        self.stop_button = tk.Button(root, text="Stop", state=tk.DISABLED, command=self.stop_audio)
        self.stop_button.pack(pady=10)

        self.speed_label = tk.Label(root, text="Playback Speed (controlled by cadence data):")
        self.speed_label.pack(pady=5)

        self.bpm_label = tk.Label(root, text="Song BPM: Unknown")
        self.bpm_label.pack(pady=5)

        self.cadence_label = tk.Label(root, text="Cadence: Unknown")
        self.cadence_label.pack(pady=5)


        self.resting_hr_label = tk.Label(root, text="Resting HR: Unknown")
        self.resting_hr_label.pack(pady=5)

        self.warmed_hr_label = tk.Label(root, text="Warmed HR: Unknown")
        self.warmed_hr_label.pack(pady=5)

        self.current_hr_label = tk.Label(root, text="Current HR: Unknown")
        self.current_hr_label.pack(pady=5)
        
        self.mode_label = tk.Label(root, text="Current Mode: warmup")
        self.mode_label.pack(pady=10)

        # Buttons for selecting modes
        self.mode_buttons_frame = tk.Frame(root)
        self.mode_buttons_frame.pack(pady=10)

        self.resting_button = tk.Button(self.mode_buttons_frame, text="Resting", command=lambda: self.set_mode("resting"))
        self.resting_button.pack(side=tk.LEFT, padx=5)

        self.warmup_button = tk.Button(self.mode_buttons_frame, text="Warmup", command=lambda: self.set_mode("warmup"))
        self.warmup_button.pack(side=tk.LEFT, padx=5)

        self.workout_button = tk.Button(self.mode_buttons_frame, text="Workout", command=lambda: self.set_mode("workout"))
        self.workout_button.pack(side=tk.LEFT, padx=5)

        self.slowdown_button = tk.Button(self.mode_buttons_frame, text="Slow Down", command=lambda: self.set_mode("slow down"))
        self.slowdown_button.pack(side=tk.LEFT, padx=5)

        self.audio_file = None
        self.current_speed = 1.0
        self.stream = None
        self.stop_flag = threading.Event()
        self.audio_data = None
        self.sample_rate = None
        self.song_bpm = None

        self.mode = "warmup"

        self.resting_hr = 60
        self.warmed_hr = 120

        self.hr_delta = self.warmed_hr - self.resting_hr
        self.hr_target = self.resting_hr + self.hr_delta * 1.5

        # Start a thread to update speed based on cadence data
        threading.Thread(target=self.update_speed_from_cadence, daemon=True).start()

    def set_mode(self, mode):
        self.mode = mode
        self.mode_label.config(text=f"Current Mode: {mode}")
        print(f"Mode set to: {mode}")

    def load_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.wav *.mp3 *.flac *.ogg")])
        if file_path:
            self.audio_file = file_path
            self.audio_data, self.sample_rate = librosa.load(file_path, sr=None)
            self.play_button.config(state=tk.NORMAL)
            print(f"Loaded {file_path}")

        self.calculate_bpm()

    def play_audio(self):
        if self.audio_data is None:
            return

        if len(self.audio_data.shape) > 1:
            self.audio_data = np.mean(self.audio_data, axis=1)

        self.stop_flag.clear()
        self.stream = threading.Thread(target=self.audio_playback, daemon=True)
        self.stream.start()
        self.stop_button.config(state=tk.NORMAL)

    def stop_audio(self):
        self.stop_flag.set()
        self.stream = None
        self.stop_button.config(state=tk.DISABLED)

    def calculate_bpm(self):
        if self.audio_data is not None:
            tempo = librosa.feature.tempo(y=self.audio_data, sr=self.sample_rate)[0]
            self.song_bpm = tempo
            self.bpm_label.config(text=f"Song BPM: {int(tempo)} BPM")
            print(f"Calculated BPM for the song: {tempo} BPM")

    def audio_playback(self):
        chunk_size = int(self.sample_rate * 0.1)
        playback_pos = 0

        try:
            with sd.OutputStream(samplerate=self.sample_rate, channels=1) as stream:
                while not self.stop_flag.is_set() and playback_pos < len(self.audio_data):
                    end_pos = min(playback_pos + chunk_size, len(self.audio_data))
                    chunk = self.audio_data[playback_pos:end_pos]
                    if len(chunk) == 0:
                        break
                    stretched_chunk = librosa.effects.time_stretch(chunk, rate=self.current_speed)
                    stream.write(stretched_chunk.astype(np.float32))
                    playback_pos = end_pos
        except sd.PortAudioError as e:
            print(f"PortAudioError: {e}")
        except Exception as e:
            print(f"Unexpected error during playback: {e}")
    
    def resting_mode(self):
        resting_hr = list()

        while self.mode == "resting":
                try:
                    hr_data = self.bluetooth_queue.get_nowait()
                except queue.Empty:
                    print("No HR data received.")
                    continue
        
                resting_hr.append(hr_data)
                resting_hr = resting_hr[-5:]
                self.resting_hr = sum(resting_hr) / 5
                self.resting_hr_label.config(text=f"Resting HR: {self.resting_hr}")
            


        self.hr_delta = self.warmed_hr - self.resting_hr
        self.hr_target = self.resting_hr + self.hr_delta * 1.5
        return
    
    def workout_mode(self, cadence_avg, hr_data):
        if hr_data < self.hr_target and cadence_avg < 180:
            new_speed = (cadence_avg + 5) / self.song_bpm
        else:
            new_speed = cadence_avg / self.song_bpm
        return new_speed
    
    def slowdown_mode(self, cadence_avg, hr_data):
        if hr_data > self.resting_hr:
            new_speed = (cadence_avg - 5) / self.song_bpm
        else:
            new_speed = cadence_avg / self.song_bpm
        return new_speed



    def update_speed_from_cadence(self):
        cadence_chunk = []

        while True:

            try:                
                try:
                    cadence_data = self.cadence_queue.get_nowait()
                except queue.Empty:
                    pass
                
                try:
                    hr_data = self.bluetooth_queue.get_nowait()
                    self.current_hr_label.config(text=f"Current HR: {hr_data}")
                except queue.Empty:
                    pass
                
                print(cadence_data)
                cadence_chunk.append(cadence_data)
                
                if len(cadence_chunk) >= 20:
                    cadence_avg = sum(cadence_chunk[-20:]) / 20
                    self.cadence_label.config(text=f"Cadence: {cadence_avg:.2f} steps/min")
                    cadence_chunk = []                
                
                
                if self.mode == "resting":
                    self.resting_mode()

                if self.song_bpm and cadence_data > 0:

                    if self.mode == "warmup":
                        new_speed = cadence_avg / self.song_bpm
                    
                    elif self.mode == "workout":
                        new_speed = self.workout_mode(cadence_avg, hr_data)

                    elif self.mode == "slow down":
                        new_speed = self.slowdown_mode(cadence_avg, hr_data)
                    
                    else:
                        new_speed = 1.0

                    self.current_speed = new_speed
                    self.speed_label.config(text=f"Playback Speed: {new_speed:.2f}x (controlled by cadence and HR data)")
                    print(f"Updated speed to {new_speed:.2f}x based on cadence and HR data.")
            except queue.Empty:
                continue
            except AttributeError as e:
                print(f"Attribute error: {e}")
                continue

    """
    def update_speed_from_cadence(self):
        cadence_chunk = []
        while True:
            try:
                print(self.cadence_queue.qsize())
                cadence_data = self.cadence_queue.get(timeout=1) if not self.cadence_queue.empty() else 0
                print(self.bluetooth_queue.qsize())
                hr_data = self.bluetooth_queue.get_nowait() if not self.bluetooth_queue.empty() else None

                print("Cadence Data: ", cadence_data)
                print("HR Data: ", hr_data)

                cadence_chunk.append(cadence_data)
                if len(cadence_chunk) >= 30:
                    cadence_avg = sum(cadence_chunk[-30:]) / 30
                    self.cadence_label.config(text=f"Cadence: {cadence_avg:.2f} steps/min")
                    cadence_chunk = []

                if self.song_bpm and cadence_avg > 0:
                    mode_functions = {
                        "resting": self.resting_mode,
                        "warmup": lambda: cadence_avg / self.song_bpm,
                        "workout": lambda: self.workout_mode(cadence_avg, hr_data),
                        "slow down": lambda: self.slowdown_mode(cadence_avg, hr_data)
                    }
                    new_speed = mode_functions.get(self.mode, lambda: 1.0)()
                    with self.lock:
                        self.current_speed = new_speed
                    self.speed_label.config(text=f"Playback Speed: {new_speed:.2f}x (controlled by cadence and HR data)")
                    print(f"Updated speed to {new_speed:.2f}x based on cadence and HR data.")

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in cadence update: {e}")
    """
# Initialize the cadence queue
cadence_queue = queue.Queue()
sock = cadence_inference.wifi_connect()



# Start the cadence thread
threading.Thread(target=cadence_inference.main, args = [sock, cadence_queue], daemon=True).start()

bluetooth_queue = queue.Queue()
threading.Thread(target=bluetooth_receive.main, args = [bluetooth_queue], daemon=True).start()

# Create the application
root = tk.Tk()
app = RealTimeAudioPlayer(root, cadence_queue, bluetooth_queue)
root.mainloop()
