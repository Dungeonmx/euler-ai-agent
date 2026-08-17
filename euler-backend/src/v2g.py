import py_audio2face as pya2f

a2f = pya2f.Audio2Face()

# Generate animation for a single audio file
a2f.audio2face_single(
    audio_file_path="../audios/audio2.mp3",  #  path of the audio file you want to animate
    output_path="../animaicones/animation.usd",  # path where the animation file will be saved
    fps=60,  # frames per second for the animation. Higher fps will result in smoother animations and longer processing time
    emotion_auto_detect=True,  # automatically detect emotions in the audio file. If false the set emotion will be used
)

# Generate animation for an entire folder of audio files
# a2f.audio2face_folder(input_folder="path/to/my/folder", output_folder='/output', fps=60)
