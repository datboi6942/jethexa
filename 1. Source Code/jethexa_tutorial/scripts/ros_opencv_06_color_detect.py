#!/usr/bin/env python3
# coding: utf8

import argparse
import sys
import rospy
import cv2
import math
import numpy as np
from sensor_msgs.msg import Image
from vision_utils import fps, get_area_max_contour, colors
from jethexa_sdk import pwm_servo

class ColorDetectNode:
    def __init__(self, target_color, log_level=rospy.INFO):
        rospy.init_node("color_detect", anonymous=True, log_level=log_level)

        self.target_color_name = target_color
        self.target_color_range = None # target color
        self.detected_color = ""

        # Get list of color thresholds from parameter server
        self.color_ranges = rospy.get_param('/lab_config_manager/color_range_list', None)
        assert(self.color_ranges is not None)
        self.target_color_range = self.color_ranges[self.target_color_name]
        rospy.loginfo("{}, {}".format(self.target_color_name, self.target_color_range))

        # Frame rate counter
        self.fps = fps.FPS()  

        # start pwm control thread
        pwm_servo.pwm_servo1.start()
        pwm_servo.pwm_servo2.start()
        pwm_servo.pwm_servo1.set_position(1500, 1000)
        pwm_servo.pwm_servo2.set_position(1500, 1000)

        # obtain image topic
        self.camera_rgb_prefix = rospy.get_param('/camera_rgb_prefix', 'camera/rgb')
        self.image_sub = rospy.Subscriber(self.camera_rgb_prefix + '/image_raw', Image, self.image_callback, queue_size=1)

        self.timer = rospy.Timer(rospy.Duration(2), self.timer_callback)
    
    def timer_callback(self, _):
        # execute the action based on whether it is the designated color
        if self.detected_color == self.target_color_name:
            for i in range(2):
                pwm_servo.pwm_servo2.set_position(1200, 200)
                rospy.sleep(0.2)
                pwm_servo.pwm_servo2.set_position(1700, 200)
                rospy.sleep(0.2)
            pwm_servo.pwm_servo2.set_position(1500, 200)
        elif self.detected_color != 'none':
            for i in range(2):
                pwm_servo.pwm_servo1.set_position(1200, 200)
                rospy.sleep(0.2)
                pwm_servo.pwm_servo1.set_position(1800, 200)
                rospy.sleep(0.2)
            pwm_servo.pwm_servo1.set_position(1500, 200)
        else:
            pass

    def image_callback(self, ros_image: Image):
        # rospy.logdebug('Received an image! ')
        # Convert ros format image to opencv format
        rgb_image = np.ndarray(shape=(ros_image.height, ros_image.width, 3), dtype=np.uint8, buffer=ros_image.data) # raw RGB image
        rgb_image = cv2.resize(rgb_image, (320, 180)) # Scale to reduce the amount of computation
        result_image = np.copy(rgb_image) # Make a copy for display of results in case the image was modified during processing
        detected_color = ""
        try:
            img_blur = cv2.GaussianBlur(rgb_image, (3, 3), 3) # Gaussian blur
            img_lab = cv2.cvtColor(img_blur, cv2.COLOR_RGB2LAB) # Convert to LAB space
            
            max_contours = []
            for color_name in ('red', 'green', 'blue'): # traverse the designated color range
                color_range = self.color_ranges[color_name]
                # Binarization
                mask = cv2.inRange(img_lab, tuple(color_range['min']), tuple(color_range['max'])) 

                # Smooth edges, remove small blocks, merge close blocks
                eroded = cv2.erode(mask, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
                dilated = cv2.dilate(eroded, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

                # find the largest contour
                contours = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)[-2]
                # The return value is (contour with largest area, contour area)
                max_contour_area = get_area_max_contour(contours, 20)
                if max_contour_area is not None:
                    max_contours.append((color_name, max_contour_area[0], max_contour_area[1]))
            
            if max_contours:
                max_contour = max(max_contours, key=lambda x: x[2]) # find the largest contour
                detected_color = max_contour[0]
            else:
                detected_color = "none"

        except Exception as e:
            rospy.logerr(str(e))
        self.detected_color = detected_color

        self.fps.update() # refresh fps stats
        result_image = self.fps.show_fps(result_image) # fps is displayed on the screen
        result_image = cv2.cvtColor(result_image, cv2.COLOR_RGB2BGR)
        cv2.imshow('image', result_image)
        cv2.waitKey(1)


if __name__ == "__main__":
    argv = rospy.myargv(argv=sys.argv)
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('target_color',  metavar="COLOR NAME", nargs='?', type=str, help="颜色名称", default='red') # the name of the color to tracked
    argv = parser.parse_args(argv[1:]) # Parse input parameters

    target_color = argv.target_color

    try:
        color_detect_node = ColorDetectNode(target_color=target_color, log_level=rospy.INFO)
        rospy.spin()
    except Exception as e:
        rospy.logerr(str(e))


