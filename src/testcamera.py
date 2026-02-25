import cv2


print("Testing ELP Camera (Overhead)...")
cap_elp = cv2.VideoCapture(0)
ret1, frame1 = cap_elp.read()
if ret1:
   cv2.imwrite("ELP_overhead_test.jpg", frame1)
   print("Saved ELP_overhead_test.jpg")
cap_elp.release()


print("Testing NexiGo N60 (Entrance)...")
cap_nexigo = cv2.VideoCapture(2)
ret2, frame2 = cap_nexigo.read()
if ret2:
   cv2.imwrite("NexiGo_entrance_test.jpg", frame2)
   print("Saved NexiGo_entrance_test.jpg")
cap_nexigo.release()


print("Camera test complete!")