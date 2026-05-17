import os
import numpy as np
import math
import time
import threading
import sys
try:
    import lunar_tools as lt
except ImportError:
    class _SimpleBuffer:
        def __init__(self, buffer_size=100, default_return_value=0):
            self.buffer_size = buffer_size
            self.default_return_value = default_return_value
            self.buffer = []

        def append(self, value):
            self.buffer.append(value)
            if len(self.buffer) > self.buffer_size:
                self.buffer.pop(0)

        def get_last(self):
            if not self.buffer:
                return self.default_return_value
            return self.buffer[-1]

        def __len__(self):
            return len(self.buffer)

        def __getitem__(self, index):
            return self.buffer[index]

    class _NumpyArrayBuffer(_SimpleBuffer):
        def append(self, value):
            super().append(np.array(value))

    class _BufferModule:
        SimpleNumberBuffer = _SimpleBuffer
        NumpyArrayBuffer = _NumpyArrayBuffer

    lt = _BufferModule()

class RigidBody:
    def __init__(self, motive_receiver, label):
        self.motive_receiver = motive_receiver
        self.label = label
        self.buffer_size = 100
        self.dt = lt.SimpleNumberBuffer(buffer_size=self.buffer_size)
        self.positions = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))
        self.velocities = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))
        # self.accelerations = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))
        # self.jerks = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))
        self.angular_velocities = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))
        self.orientations = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(4))
        self.euler_angles = lt.NumpyArrayBuffer(buffer_size=self.buffer_size, default_return_value=np.zeros(3))

        self.forces = []
        self.buffer_size = 1000

        self.corners_x = [3.1, -3.5]
        self.corners_y = [0, 2]
        self.corners_z = [-2.1, 3.1]
        self.fract_xz = np.zeros(2)
        self.fract_xyz = np.zeros(3)
        self.t_last = 0
        self.t_current = 0
        
        # self.v_current = np.array([0, 0, 0])
        # self.v_last = np.array([0, 0, 0])
        # self.a_current = [0, 0, 0]
        # self.a_last = [0, 0, 0]


    def update(self):
        rigid_bodies_data = self.motive_receiver.get_last("rigid_bodies_full")
        if rigid_bodies_data is None:
            return False
        if self.label not in rigid_bodies_data:
            return False
        body_data = rigid_bodies_data[self.label]
        self.t_last = self.t_current
        self.t_current = self.motive_receiver.get_last_timestamp()
        dt = self.t_current - self.t_last
        if dt == 0:
            # print("WARNING! dt between packages is zero!! returning...")
            # there is nothing to do. return!
            return False
        self.dt.append(dt)
        position = np.array(body_data["pos"])
        self.positions.append(position)

        orientation = np.array(body_data["rot"])
        self.orientations.append(orientation)
        self.euler_angles.append(euler_from_quaternion(*orientation))

        if len(self.euler_angles.buffer) >= 2:

            # angular_velocity = self.euler_angles.get_last()[-1] - self.euler_angles.get_last()[-2]

            angular_velocity = self.euler_angles.buffer[-1] - self.euler_angles.buffer[-2]

            self.angular_velocities.append(angular_velocity)

        if len(self.positions.buffer) <= 2:
            return True
        
        if len(self.positions.buffer) >= 2:
            v_current = (self.positions.buffer[-1] - self.positions.buffer[-2]) / dt
            self.velocities.append(v_current)

        self.get_xz_fract()
        self.get_xyz_fract()
        return True

    def has_data(self):
        return len(self.positions.buffer) > 0

    def get_position(self):
        self.update()
        return self.positions.get_last()

    def get_rotation(self):
        self.update()
        return self.orientations.get_last()

    def get_velocity(self):
        self.update()
        return self.velocities.get_last()


    def get_xz_fract(self):
        if len(self.positions.buffer) > 1:
            current_x = self.positions.get_last()[0]
            current_z = self.positions.get_last()[2]

            self.fract_xz[0] = get_fract(self.corners_x[0], self.corners_x[1], current_x)
            self.fract_xz[1] = get_fract(self.corners_z[0], self.corners_z[1], current_z)

    def get_xyz_fract(self):
        if len(self.positions.buffer) > 1:
            current_x = self.positions.get_last()[0]
            current_y = self.positions.get_last()[1]
            current_z = self.positions.get_last()[2]
            
            # print(f'current_y {current_y}')

            self.fract_xyz[0] = get_fract(self.corners_x[0], self.corners_x[1], current_x)
            self.fract_xyz[1] = get_fract(self.corners_y[0], self.corners_y[1], current_y)
            self.fract_xyz[2] = get_fract(self.corners_z[0], self.corners_z[1], current_z)





class BodyTracker:
    """
    This class provides a minimal way to get relative hand positions to the heart center.
    It uses the Motive software"s tracking data to calculate the positions of the hands relative to the heart center.
    The positions are updated in real-time as the Motive software tracks the movement of the hands and the heart center.
    """
    def __init__(self, motive):
        self.motive = motive
        self._head = RigidBody(self.motive, "C")
        self._left_hand = RigidBody(self.motive, "A")
        self._right_hand = RigidBody(self.motive, "B")
        self.offset_heart = np.array([0, -0.45, 0])
        self.positions_heart = []
        self.positions_left_hand = []
        self.positions_right_hand = []
        

    def update(self):
        # First update all raw rigid bodies
        self._head.update()
        self._left_hand.update()
        self._right_hand.update()
        
        # Then compute heart center
        if len(self._head.positions) > 1:
            self.positions_heart.append(self._head.positions[-1] + self.offset_heart)
        
        # Then get relative positions for the left and right hand
        if len(self._left_hand.positions) > 1:
            lh = self._left_hand.positions[-1] - self.positions_heart[-1]
            lh[0] = -lh[0]
            self.positions_left_hand.append(lh)
        if len(self._right_hand.positions) > 1:
            rh = self._right_hand.positions[-1] - self.positions_heart[-1]
            rh[0] = -rh[0]
            self.positions_right_hand.append(rh)
            
            # self.positions_heart.append(self._head.positions[-1] + self.offset_heart)


def euler_from_quaternion(x, y, z, w):
    """
    Convert a quaternion into euler angles (roll, pitch, yaw)
    roll is rotation around x in radians (counterclockwise)
    pitch is rotation around y in radians (counterclockwise)
    yaw is rotation around z in radians (counterclockwise)
    """
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll_x = math.atan2(t0, t1)
 
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch_y = math.asin(t2)
 
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = math.atan2(t3, t4)
    
    euler_angles = np.array([roll_x, pitch_y, yaw_z])
 
    return euler_angles # in radians

def get_fract(val_fract0, val_fract1, val):
    do_swap = False
    # Check if val_fract0 is larger than val_fract1
    if val_fract0 > val_fract1:
        do_swap = True
        val_fract0, val_fract1 = val_fract1, val_fract0

    # Check if val is within the range of val_fract0 and val_fract1
    if val_fract0 <= val <= val_fract1:
        # Calculate the fraction of the distance val is between val_fract0 and val_fract1
        fract = (val - val_fract0) / (val_fract1 - val_fract0)
    else:
        # If val is outside the range, return 0 or 1 depending on which side it's closer to
        fract = 0 if val < val_fract0 else 1

    if do_swap:
        fract = 1-fract
    return fract


if __name__ == "__main__":
    from optitrack_motive.motive_receiver import MotiveReceiver
    
    # Use the exact same setup as the working motive_receiver.py example
    print("Connecting to OptiTrack...")
    motive = MotiveReceiver(server_ip="10.40.49.47")
    
    print("Waiting for data connection...")
    time.sleep(1)
    
    # Test basic connection first
    print("Testing basic connection...")
    for i in range(50):  # Try for 5 seconds
        latest_data = motive.get_last()
        if latest_data:
            print(f"✓ Connection established! Frame ID: {latest_data['frame_id']}")
            break
        time.sleep(0.1)
    else:
        print("✗ No data received. Check OptiTrack connection.")
        motive.stop()
        exit(1)
    
    # Create a single rigid body "B" for demonstration
    rigid_body = RigidBody(motive, "A")
    
    print("Starting rigid body tracking for 'B'...")
    frame_count = 0
    
    try:
        while True:
            time.sleep(0.1)  # Same as motive_receiver example
            frame_count += 1
            
            latest_data = motive.get_last()
            if not latest_data:
                continue
                
            # Print raw data like motive_receiver does for comparison
            if frame_count % 10 == 1:  # Every second
                print(f"\nFrame ID: {latest_data['frame_id']}")
                print(f"Timestamp: {latest_data['timestamp']}")
                if 'rigid_bodies_full' in latest_data and latest_data['rigid_bodies_full']:
                    print("Raw Rigid Bodies:")
                    for name, body in latest_data['rigid_bodies_full'].items():
                        pos = body.get('pos')
                        print(f"  {name}: Position {pos}")
            
            # Now try to use our RigidBody class
            rigid_body.update()
            position = rigid_body.positions.get_last()
            
            # Only print if we got real data (not zeros)
            if not np.allclose(position, [0, 0, 0]):
                print(f"RigidBody processed position: {position}")
                
                if len(rigid_body.velocities.buffer) > 0:
                    velocity = rigid_body.velocities.get_last()
                    print(f"RigidBody velocity: {velocity}")
                
                orientation = rigid_body.orientations.get_last()
                print(f"RigidBody orientation: {orientation}")
                
                print("-" * 30)
                
    except KeyboardInterrupt:
        print("\nStopping...")
        motive.stop()
