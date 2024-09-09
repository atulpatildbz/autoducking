# Auto Duck

This script provides functionality to automatically apply audio ducking to a music track based on the presence of a voiceover.

## Requirements

Before using this script, ensure you have the following packages installed:

- subprocess (usually comes with Python)
- json (usually comes with Python)
- numpy
- pydub
- ffmpeg (command-line tool)
- ffprobe (usually comes with ffmpeg)


## Usage

To use the Auto Duck script, follow these steps:

1. Ensure you have all the required packages installed.
2. Place your music file and voiceover file in the same directory as the script.
3. Edit the `voiceover_file`, `music_file` and `output_file` variables in the script.
3. Run the script from the command line using the following format:

   ```
   python auto_duck.py
   ```

4. The script will process the files and create a new audio file with the music ducked during the voiceover.
