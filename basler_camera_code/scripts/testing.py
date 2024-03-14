from pypylon import pylon
import cv2


def main():
    cameras = []
    for i in pylon.TlFactory.GetInstance().EnumerateDevices():
        cameras.append(i)

    camera1 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(cameras[0]))
    camera2 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(cameras[1]))
    camera1.Open()
    camera2.Open()
    camera1.StopGrabbing()
    camera2.StopGrabbing()
   


    try:
        while True:
            # Trigger both cameras simultaneously
            camera1.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
            camera2.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)

            # Retrieve frames from both cameras
            grab_result1 = camera1.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
            grab_result2 = camera2.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)

            if grab_result1.GrabSucceeded() and grab_result2.GrabSucceeded():
                # Convert frames to OpenCV format
                frame1 = grab_result1.Array
                frame2 = grab_result2.Array

                # Process or display frames as needed
                cv2.imshow("Camera 1", frame1)
                cv2.imshow("Camera 2", frame2)

            # Release grab results for both cameras
            grab_result1.Release()
            grab_result2.Release()

            # Check for exit key press
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        # Stop grabbing and close cameras
        camera1.StopGrabbing()
        camera2.StopGrabbing()
        camera1.Close()
        camera2.Close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()