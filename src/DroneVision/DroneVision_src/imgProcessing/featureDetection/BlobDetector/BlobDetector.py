'''
 Author: Hans Erik Heggem
 Email: hans.erik.heggem@gmail.com
 Project: Master's Thesis - Autonomous Inspection Of Wind Blades
 Repository: Master's Thesis - CV (Computer Vision
'''
import cv2, math, operator
import numpy as np

from Settings.Exceptions import DroneVisionError
from src.DroneVision.DroneVision_src.imgProcessing.frameTools.frameTools import PyrDown, GetShape
from src.DroneVision.DroneVision_src.hardware.imageTools import MatplotShow
from src.DroneVision.DroneVision_src.imgProcessing.CameraCalibration.StereoVision import StereoVision

'''
 @brief Detect blobs in image. Specialized for detecting points.
 	See: https://www.learnopencv.com/blob-detection-using-opencv-python-c/
	See: http://docs.opencv.org/trunk/d0/d7a/classcv_1_1SimpleBlobDetector.html

	from http://docs.opencv.org/trunk/d0/d7a/classcv_1_1SimpleBlobDetector.html:
	 	Class for extracting blobs from an image (SimpleBlobDetector). :

		The class implements a simple algorithm for extracting blobs from an image:

		Convert the source image to binary images by applying thresholding with several thresholds from minThreshold (inclusive) to maxThreshold (exclusive) with distance thresholdStep between neighboring thresholds.
		Extract connected components from every binary image by findContours and calculate their centers.
		Group centers from several binary images by their coordinates. Close centers form one group that corresponds to one blob, which is controlled by the minDistBetweenBlobs parameter.
		From the groups, estimate final centers of blobs and their radiuses and return as locations and sizes of keypoints.
		This class performs several filtrations of returned blobs. You should set filterBy* to true/false to turn on/off corresponding filtration. Available filtrations:

		By color. This filter compares the intensity of a binary image at the center of a blob to blobColor. If they differ, the blob is filtered out. Use blobColor = 0 to extract dark blobs and blobColor = 255 to extract light blobs.
		By area. Extracted blobs have an area between minArea (inclusive) and maxArea (exclusive).
		By circularity. Extracted blobs have circularity ( 4*pi*Area/(perimeter*perimeter)) between minCircularity (inclusive) and maxCircularity (exclusive).
		By ratio of the minimum inertia to maximum inertia. Extracted blobs have this ratio between minInertiaRatio (inclusive) and maxInertiaRatio (exclusive).
		By convexity. Extracted blobs have convexity (area / area of blob convex hull) between minConvexity (inclusive) and maxConvexity (exclusive).
		
		Default values of parameters are tuned to extract dark circular blobs.

 @param me_master (True if this is the Master instance, False for slave instance)
 @param calib_settings_inst (CALIB settings)
 @param default_downsampling_divisor (Default divisor for downsampling frames)
 @param desired_frame_shape (desired frame shape of processed frames. Incoming frames are matched to fit this shape. Given as a tuple of (height, width). Set (-1,-1) to fix downscaling to the default_downsampling_divisor.)
 @param reset (True/False)
 @param detector_type (	flag for which detector to use: 
		 						0 = Simple blob detector (default)
		 						1 = ORB detector
		 						2 = SIFT detector
		 						3 = SURF detector)
 @param plot_figure (optional plot figure (default=None))
'''
class BlobDetector(StereoVision):
	def __init__(self, me_master, calib_settings_inst, default_downsampling_divisor, desired_frame_shape, reset, detector_type=0, plot_figure=None):
		'''COSNTRUCTOR'''
		StereoVision.__init__(self, me_master, calib_settings_inst, reset, plot_figure=plot_figure)
		self.__default_downsampling_divisor = default_downsampling_divisor
		self.__desired_frame_shape 		= desired_frame_shape
		self.__detector_type 			= detector_type

		# Setup SimpleBlobDetector parameters.
		self.__blob_params = cv2.SimpleBlobDetector_Params()
		 
		# Change thresholds
		self.__blob_params.minThreshold = 1
		self.__blob_params.maxThreshold = 255

		# Change minimum distance between blobs
		self.__blob_params.minDistBetweenBlobs = 1

		# Filter by Color
		self.__blob_params.filterByColor = True
		self.__blob_params.blobColor = 255
		 
		# Filter by Area.
		self.__blob_params.filterByArea = False
		self.__blob_params.minArea = 10
		 
		# Filter by Circularity
		self.__blob_params.filterByCircularity = False
		self.__blob_params.minCircularity = 0.01
		 
		# Filter by Convexity
		self.__blob_params.filterByConvexity = False
		self.__blob_params.minConvexity = 0.5
		 
		# Filter by Inertia
		self.__blob_params.filterByInertia = False
		self.__blob_params.minInertiaRatio = 0.02
		 
		# Create a detector with the parameters
		self.__keypoint_detector 								= self.ComputeFeatureDetector(self.__blob_params, self.__detector_type)
		self.__descriptor_detector, self.__descriptor_available = self.ComputeFeatureDescriptor()

		# Create scale detector 
		self.__minDistBetweenBlobs_calibrated = False

	def GetBlobParams(self):
		'''
		 @brief Get blob parameters

		 @return blob_params
		'''
		return self.__blob_params

	def GetMinDistanceBetweenBlobs(self):
		'''
		 @brief Get minimum distance between blobs

		 @return minDistBetweenBlobs
		'''
		self.AssertBlobDistanceCalibrated()
		return self.__min_distance_between_blobs

	def GetBlobDistanceCalibrated(self):
		'''
		 @brief Get blob distance calibrated

		 @return True/False
		'''
		return self.__minDistBetweenBlobs_calibrated

	def AssertBlobDistanceCalibrated(self):
		'''
		 @brief Assert that the blob distance is calibrated
		 	Raises exception blob_distance_is_not_calibrated_error_msg if the standard blob distance isn't calibrated.
		'''
		if not(self.__minDistBetweenBlobs_calibrated):
			raise DroneVisionError('blob_distance_is_not_calibrated_error_msg')

	def ComputeFeatureDetector(self, params, detector_type=0):
		'''
		 @brief Compute keypoint detector with given params.

		 @param params Parameters for the keypoint detector
		 @param detector_type (	flag for which detector to use: 
		 						0 = Simple blob detector (default)
		 						1 = ORB detector
		 						2 = SIFT detector
		 						3 = SURF detector)

		 @return keypoint_detector
		'''
		if detector_type == 0:
			keypoint_detector = cv2.SimpleBlobDetector_create(self.__blob_params)
		elif detector_type == 1:
			keypoint_detector = cv2.ORB_create()
		elif detector_type == 2:
			keypoint_detector = cv2.xfeatures2d.SIFT_create()
		elif detector_type == 3:
			keypoint_detector = cv2.xfeatures2d.SURF_create()
		else:
			raise ValueError('Invalid detector type flag: {0}. Options are 0, 1, 2, 3 for simple blob detector, ORB, SIFT or SURF (in that order).')
		return keypoint_detector

	def ComputeFeatureDescriptor(self):
		'''
		 @brief Compute descriptor detector
		 	The SIFT descriptor are in the contribution packages to opencv, so it might cause problems.

		 @return descriptor_detector, available (Returns descriptor_detector, available - (True/False to flag if the descriptor detector is available))
		'''
		available = True
		try:
			descriptor_detector = cv2.xfeatures2d.SIFT_create()
		except:
			available = False
			descriptor_detector = None
		return descriptor_detector, available

	def AssertFeatureDesctriptorAvailable(self):
		'''
		 @brief Assert that the feature descriptor is available
		 	Raises exception feature_descriptor_not_available_error_msg if it isn't available.
		'''
		if not(self.__descriptor_available):
			raise DroneVisionError('feature_descriptor_not_available_error_msg')

	def CalibrateBlobDetector(self, min_distance_between_blobs):
		'''
		 @brief Calibrate minimum distance between blobs using a standard frame with and without structural light points.

		 @param min_distance_between_blobs (Minimum distance between blobs estimate)
		'''
		self.__min_distance_between_blobs 		= min_distance_between_blobs
		self.__blob_params.minDistBetweenBlobs 	= min_distance_between_blobs*0.5
		# Recreate a keypoint detector with the new parameters
		self.__keypoint_detector = self.ComputeFeatureDetector(self.__blob_params, self.__detector_type)
		self.__minDistBetweenBlobs_calibrated = True

	def DetectBlobs(self, frame, compute_descriptors=False):
		'''
		 @brief Detect blobs (points) in a frame.

		 @param frame
		 @param compute_descriptors (Default=False)

		 @return keypoints, descriptors (Returns keypoints = blob keypoints as a list, descriptors = blob descriptors as a list
		 	Position and size of blob is found by:
		 	for blob in keypoints:
		 		blob.pt[0] #x
		 		blob.pt[1] #y
		 		blob.size  #size )
		'''
		# Detect blobs. Frame consist only of highlighted points (blobs), so mask is equal to the frame (mask shows all points of interest which is all non-zero values).
		keypoints = self.__keypoint_detector.detect(frame, mask=frame)
		if compute_descriptors:
			self.AssertFeatureDesctriptorAvailable()
			keypoints, descriptors = self.__descriptor_detector.compute(frame, keypoints=keypoints)
		else:
			descriptors = np.zeros(len(keypoints))
		if len(keypoints) == 0:
			raise DroneVisionError('no_blobs_error_msg')
		return keypoints, descriptors

	def GetDefaultPyrDownDivisor(self):
		'''
		 @brief Get default donwsample divisor

		 @return pyr_down_divisor
		'''
		return self.__default_downsampling_divisor

	def GetDesiredFrameShape(self):
		'''
		 @brief Get desired frame shape given as (height, width) tuple.

		 @return desired_frame_shape
		'''
		return self.__desired_frame_shape

	def GetPointList(self, frame, sl_frame, undistort=True, concatenate_points=False, compute_descriptors=False, draw=False):
		'''
		 @brief Steps for computing point list from a normal frame and structured light frame.
		 		Undistorts (at request) and scales down the frames. 
		
		 @param frame (normal frame (grayscale) - raw (not manipulated))
		 @param sl_frame (structured light frame (grayscale) - raw (not manipulated))
		 @param undistort (True/False on undistorting frames (default=True))
		 @param concatenate_points (True/False on concatenating close points (default=False))
		 @param compute_descriptors (default=False)
		 @param draw (True/False)

		 @return delta_frame, keypoints, descriptors, frame, sl_frame 
		 		(Returns: 
		 		delta_frame = frame with highlighted points above threshold. 
				keypoints = all point positions above threshold (2D numpy array = each row is a point position [x, y]).
				descriptors = point descriptors
				frame = updated frame
				sl_frame = updated sl_frame
				)
		'''
		pyr_down_divisor 	= self.GetDefaultPyrDownDivisor()
		desired_frame_shape = self.GetDesiredFrameShape()

		frame 			 = PyrDown(frame, pyr_down_divisor, desired_frame_shape)
		sl_frame 		 = PyrDown(sl_frame, pyr_down_divisor, desired_frame_shape)

		if undistort:
			frame 		= self.Undistort(frame)
			sl_frame 	= self.Undistort(sl_frame)

		delta_frame, keypoints, descriptors = self.DeltaFrame(frame, sl_frame, concatenate_points=concatenate_points, compute_descriptors=compute_descriptors, draw=draw)
		return delta_frame, keypoints, descriptors, frame, sl_frame

	def DeltaFrame(self, frame, sl_frame, threshold=50, concatenate_points=False, compute_descriptors=False, draw=False):
		'''
		 @brief Computes the delta (change) between the frame without structured light, and with structured light.

		 @param frame Frame without structured light.
		 @param sl_frame Frame with structured light.
		 @param threshold Simple high pass filter which removes all pixels below the threshold value and sets all pixels above the threshold to 255.
		 @param concatenate_points (True for concatenating close points which are within a close distance (default=False))
		 @param compute_descriptors (default=False)
		 @param draw Draw detected points on frame

		 @return delta_frame, keypoints, descriptors (Returns delta_frame = frame with highlighted points above threshold. 
										keypoints = all point positions above threshold (list of keypoints).
										descriptors = point descriptors)
		'''
		origin_type = frame.dtype
		frame 		= frame.astype(int)
		sl_frame 	= sl_frame.astype(int)
		delta_frame = np.abs(frame - sl_frame)
		low_indices = delta_frame < threshold
		delta_frame[low_indices] = 0
		max_indices = delta_frame >= threshold
		delta_frame[max_indices] = 255

		delta_frame = delta_frame.astype(origin_type)
		frame 		= frame.astype(origin_type)
		sl_frame 	= sl_frame.astype(origin_type)

		keypoints, descriptors	= self.DetectBlobs(delta_frame, compute_descriptors=compute_descriptors)
		if concatenate_points:
			keypoints, descriptors = self.ConcatenateClosePoints(keypoints, descriptors)

		if draw:
			delta_frame = self.DrawKeypoints(delta_frame, keypoints)

		return delta_frame, keypoints, descriptors

	def ConcatenateClosePoints(self, keypoints, descriptors, copy_to_new_keypoints=False):
		'''
		 @brief Concatenate close points which are within a close distance.

		 @param keypoints
		 @param descriptors
		 @param copy_to_new_keypoints Create new copy of point list, or manipulate old one. (Default = True)

		 @return conc_points, conc_points_desc
		'''
		conc_points 		= []
		conc_points_desc 	= []
		if copy_to_new_keypoints:
			cp_keypoints = list(keypoints)
		else:
			cp_keypoints = keypoints
		descriptors_type = str(descriptors.dtype)
		cp_point_desc = descriptors.tolist()

		if self.GetBlobDistanceCalibrated():
			max_threshold = self.GetMinDistanceBetweenBlobs()*0.5
		else:
			biggest_size = 0
			for i in range(len(cp_keypoints)):
				if cp_keypoints[i].size > biggest_size:
					biggest_size = cp_keypoints[i].size
			max_threshold = biggest_size*2

		while len(cp_keypoints) > 0:
			point 		= cp_keypoints.pop()
			point_desc 	= cp_point_desc.pop()
			j = 0
			while j < len(cp_keypoints):
				if j == 0:
					min_vec_dist = math.sqrt(math.pow(point.pt[0] - cp_keypoints[j].pt[0], 2) + math.pow(point.pt[1] - cp_keypoints[j].pt[1], 2))
					min_index = j
				else:
					s_min_ved_dist = math.sqrt(math.pow(point.pt[0] - cp_keypoints[j].pt[0], 2) + math.pow(point.pt[1] - cp_keypoints[j].pt[1], 2))
					if s_min_ved_dist < min_vec_dist:
						min_vec_dist = s_min_ved_dist
						min_index = j
				j += 1
			if min_vec_dist <= max_threshold and len(cp_keypoints) > 0:
				if point.size < cp_keypoints[min_index].size:
					point 		= cp_keypoints.pop(min_index)
					point_desc 	= cp_point_desc.pop(min_index)
				else:
					cp_keypoints.pop(min_index)
					cp_point_desc.pop(min_index)
			conc_points.append(point)
			conc_points_desc.append(point_desc)
		return conc_points, np.array(conc_points_desc, dtype=descriptors_type)

	def DrawKeypoints(self, frame, keypoints, create_new_frame=False, color=(255,0,0), draw_rich_keypoints=True):
		'''
		 @brief Draw keypoints on frame
			
		 @param frame
		 @param keypoints (list of cv2 keypoints)
		 @param create_new_frame (Create new frame to draw on (default=False))
		 @param color (tuple of colors as rgb (default=(255,0,0)))
		 @param draw_rich_keypoints (Draw keypoints according to rotation and size (default=True))

		 @param frame (colored frame with keypoints)
		'''
		flags = 0
		if draw_rich_keypoints:
			flags += cv2.DRAW_MATCHES_FLAGS_DRAW_RICH_KEYPOINTS
		if create_new_frame:
			kp_frame = np.zeros(GetShape(frame), dtype=np.uint8)
		else:
			kp_frame = frame
			flags 	+= cv2.DRAW_MATCHES_FLAGS_DRAW_OVER_OUTIMG
		kp_frame = cv2.drawKeypoints(kp_frame, keypoints, kp_frame, color=color, flags=flags)
		return kp_frame