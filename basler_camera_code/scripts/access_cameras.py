from pypylon import pylon

"""
tl_factory = pylon.TlFactory.GetInstance()
devices = tl_factory.EnumerateDevices()
for device in devices:
    print(device.GetFriendlyName())
"""

from pypylon import pylon
import cv2

def main():
    # Create an instant camera object
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())

    # Open the camera
    camera.Open()

    # Set camera parameters
    camera.Width.SetValue(1920)  # Set width
    camera.Height.SetValue(1020)  # Set height
    camera.ExposureTime.SetValue(10000)  # Set exposure time in microseconds (e.g., 10 ms)
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(30)  # Set FPS (e.g., 30 frames per second)

    # Create a CV2 window
    cv2.namedWindow("Motion Detection", cv2.WINDOW_NORMAL)

    # Initialize variables for storing previous frame
    prev_frame = None

    try:
        # Start grabbing images from the camera
        camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

        while camera.IsGrabbing():
            # Retrieve a grabbed image
            grab_result = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grab_result.GrabSucceeded():
                # Convert the grabbed image to OpenCV format
                frame = grab_result.Array
                print(frame.shape)

                # Convert the frame to grayscale
                # gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                if prev_frame is not None:
                    # Compute absolute difference between current and previous frame
                    diff_frame = cv2.absdiff(prev_frame, frame)

                    # Apply threshold to highlight significant changes
                    _, thresh = cv2.threshold(diff_frame, 10, 255, cv2.THRESH_BINARY)

                    # Display the thresholded image
                    cv2.imshow("Motion Detection", thresh)

                # Store the current frame as previous frame for the next iteration
                prev_frame = frame.copy()

            # Wait for a key press to exit
            key = cv2.waitKey(1)
            if key & 0xFF == ord('q'):
                break

    finally:
        # Stop grabbing images
        camera.StopGrabbing()

        # Close the camera
        camera.Close()

        # Close the OpenCV window
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

