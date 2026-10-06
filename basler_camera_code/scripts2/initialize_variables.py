from camera_pair_initialization import ini_cam_pair


def ini_var():
    paradigm = input("What paradigm will you record?\n")
    modules = list(input("What modules will be used? If using module 1 & 2, type: 12\n"))
    
    
    frames = []
    prev_frames = []
    movement_present = []
    all_cams = []
    camera_pairs_list = []


    if '1' in modules:
        try:
            cameras1 = ini_cam_pair(module_num=1)
            all_cams = all_cams + cameras1
            camera_pairs_list.append(cameras1)
        except:
            print("Could not create first camera module.")
    
    if '2' in modules:
        try:
            cameras2 = ini_cam_pair(module_num=2)
            all_cams = all_cams + cameras2
            camera_pairs_list.append(cameras2)
        
        except:
            print("Could not create second camera module.")
        

    if '3' in modules:
        try:
            cameras3 = ini_cam_pair(module_num=3)
            all_cams = all_cams + cameras3
            camera_pairs_list.append(cameras3)
        except:
            print("Could not create third camera module.")


    for _ in range(len(camera_pairs_list)):
        frames.append(None)
        prev_frames.append(None)
        movement_present.append(False) 
    return paradigm, modules, frames, prev_frames, movement_present, all_cams, camera_pairs_list