import cv2
from pypylon import pylon

def main():
    # Connect to the camera
    camera = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateFirstDevice())
    camera.Open()

    # Start grabbing frames
    camera.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

    # Set up video writer
    fourcc = cv2.VideoWriter_fourcc(*'XVID')  # Define the codec
    out = cv2.VideoWriter('output.avi', fourcc, 30.0, (camera.Width.Value, camera.Height.Value))

    while camera.IsGrabbing():
        grabResult = camera.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

        if grabResult.GrabSucceeded():
            # Convert the grabbed image to numpy array
            img = grabResult.Array

            if len(img.shape) == 2:
            # Convert grayscale to BGR format
                
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            # Write the frame to the video file
            out.write(img)

            # Display the frame if needed
            cv2.imshow('Frame', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        grabResult.Release()

    # Release everything when done
    camera.StopGrabbing()
    camera.Close()
    out.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
