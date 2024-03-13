def set_camera_parameters(camera, exposuretime = int, fps = int, width = 1920, height = 1080):
    """
    Sets the exposure time and frames per second of an camera object.
    Note: exposure time is given in MICROseconds (e.g. 10 ms --> 10000 µs)
    """
    camera.ExposureTime.SetValue(exposuretime)  # Set exposure time in microseconds (e.g., 10 ms)
    camera.AcquisitionFrameRateEnable.SetValue(True)
    camera.AcquisitionFrameRate.SetValue(fps)
    # set width and height, max. of the basler Aca1920-150um is 1984x1264
    camera.Width.SetValue(width)  
    camera.Height.SetValue(height) 