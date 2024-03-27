from pypylon import pylon
import cv2


#cv2.namedWindow("Camera 1", cv2.WINDOW_NORMAL)
#cv2.namedWindow("Camera 2", cv2.WINDOW_NORMAL)

infos = []
for i in pylon.TlFactory.GetInstance().EnumerateDevices():
    infos.append(i)


camera1 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(infos[0]))
camera2 = pylon.InstantCamera(pylon.TlFactory.GetInstance().CreateDevice(infos[1]))
camera1.Open()
camera2.Open()
camera1.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
camera2.StartGrabbing(pylon.GrabStrategy_LatestImageOnly)
while camera1.IsGrabbing():
    grab_result = camera1.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    grab_result2 = camera2.RetrieveResult(5000, pylon.TimeoutHandling_ThrowException)
    frame = grab_result.Array
    frame2 = grab_result2.Array
    cv2.imshow("Camera 1", frame)
    cv2.imshow("Camera 2", frame2)

    key = cv2.waitKey(1)
    if key & 0xFF == ord('q'):
        break

camera1.StopGrabbing()
camera2.StopGrabbing()

        
camera1.Close()
camera2.Close()


cv2.destroyAllWindows()