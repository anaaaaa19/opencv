## WHAT YOU SHOULD KNOW

## Libraries to make everything work 
1.	Open CV
2.	Mediapipe – Hand tracking library 
3.	Numpy – It is the math library 
4.	Threading – mediapipe run on a separate library 
5.	Subprocess – for python to run powershell commands

## The volume control is through Powershell
(as pycaw wasn’t the best option here)
The windows powershell is called directly 
[char]175 and [char]174 is for volume up and volume down respectively 
For the volume, it is important to ensure that the percent simply stays between 0 and 100
Max .. – stops it from going below 0  Min..- stops it from going above 100
The formula of difference is diff = percent – (the assumed volume)
If the difference is positive then the volume goes up or else it goes down.
In general pressing the key increases the or decreases the volume by 2% so if the difference is simply 10, then we press 5 times and hence the code uses the given formula of ## presses

## Powershell
Popen – it doesn’t wait for the powershell to finish and ensures that the camera does not freeze while the volume changes 
Stdout – hiding the powershell outputs 
Stderr – hiding the powershell errors 

The code also includes some shortcuts like BaseOptions,HandLandmarker etc

Lock is important as the data could get corrupted without it and the lock makes sure only one thread touches it at a time.
LIVE_STREAM – processing of the frames as fast as possible
Confidence threshold – How sure mediapipe has to be?

## Smoother
Smoother class – hands naturally shake a little bit, without this, the cursor jumps all over 
If the side values exceed, pop is used which ensures that the oldest item is removed and this is called as sliding window 
It keeps the last 6 positions in memory
Two smoothers are created for X and Y axis as they are independent of each other 
Frame 1: position = 100
Frame 2: position = 103
Frame 3: position = 98
Frame 4: position = 102
Frame 5: position = 101
Frame 6: position = 99
The Avg is given by:
Average = (100+103+98+102+101+99) / 6 = 100.5

## Finger counter
Looks at the 21 hand landmarks and figures out how many fingers are raised
Each fingertip has its Landmark ID as mentioned in the code 
If the tip Y coordinate is less than the base Y coordinate the finger is pointing up, if thumb tip X is less than the joint below it the thumb is extended outward

## Tap detector 
Detects when you tap a key on the keyboard
A tap = index finger dips below middle finger

# SETUP 

## 1. Install libraries
pip install opencv-python mediapipe numpy
## 2. Download the AI model
curl -o hand_landmarker.task "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
## 3. Run
python opencv.py
