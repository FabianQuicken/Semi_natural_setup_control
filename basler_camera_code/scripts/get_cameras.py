from pypylon import pylon

cameras = []
for i in pylon.TlFactory.GetInstance().EnumerateDevices():
    cameras.append(i)

print(cameras[0].GetSerialNumber())