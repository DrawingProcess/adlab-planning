import numpy as np
import math
import matplotlib.pyplot as plt

from map.parking_lot import ParkingLot
from map.complex_grid_map import ComplexGridMap
from route_planner.informed_trrt_star_planner import Pose, InformedTRRTStar
from utils import calculate_angle, transform_arrays_with_angles

class MPCController:
    def __init__(self, horizon, dt, map_instance, wheelbase):
        self.horizon = horizon
        self.dt = dt
        self.map_instance = map_instance
        self.wheelbase = wheelbase  # Wheelbase of the vehicle

    def predict(self, state, control_input):
        x, y, theta, v = state
        v_ref, delta_ref = control_input

        # Update the state using the kinematic bicycle model
        x += v * np.cos(theta) * self.dt
        y += v * np.sin(theta) * self.dt
        theta += v / self.wheelbase * np.tan(delta_ref) * self.dt
        v += v_ref * self.dt

        return np.array([x, y, theta, v])

    def compute_cost(self, predicted_states, ref_trajectory):
        cost = 0
        for i in range(len(predicted_states)):
            if i >= len(ref_trajectory):
                break
            state = predicted_states[i]
            ref_state = ref_trajectory[i]
            cost += np.sum((state - ref_state)**2)
        return cost

    def is_collision_free(self, state):
        x, y, _, _ = state
        return self.map_instance.is_not_crossed_obstacle((round(x), round(y)), (round(x), round(y)))

    def optimize_control(self, current_state, ref_trajectory):
        best_control = None
        min_cost = float('inf')

        for v_ref in np.linspace(-1, 1, 7):  # Increased resolution for finer control
            for delta_ref in np.linspace(-np.pi/6, np.pi/6, 7):  # Adjusted steering angle range
                predicted_states = []
                state = current_state
                for _ in range(self.horizon):
                    state = self.predict(state, (v_ref, delta_ref))
                    predicted_states.append(state)

                # Ensure that the predicted states and reference trajectory have matching lengths
                if len(predicted_states) > len(ref_trajectory):
                    predicted_states = predicted_states[:len(ref_trajectory)]

                if all(self.is_collision_free(s) for s in predicted_states):
                    cost = self.compute_cost(predicted_states, ref_trajectory)
                    if cost < min_cost:
                        min_cost = cost
                        best_control = (v_ref, delta_ref)

        # If no control was found, default to a small forward motion
        if best_control is None:
            best_control = (0.1, 0.0)

        return best_control

    def apply_control(self, current_state, control_input):
        return self.predict(current_state, control_input)
    
    def follow_trajectory(self, start_pose, ref_trajectory):
        """
        Follow the reference trajectory using the MPC controller.
        
        Parameters:
        - start_pose: The starting pose (Pose object).
        - ref_trajectory: The reference trajectory (numpy array).
        
        Returns:
        - trajectory: The trajectory followed by the MPC controller (numpy array).
        """
        # Initialize the state and trajectory
        start_pose.theta = calculate_angle(start_pose.x, start_pose.y, ref_trajectory[1, 0], ref_trajectory[1, 1])
        current_state = np.array([start_pose.x, start_pose.y, start_pose.theta, 0.0])
        trajectory = [current_state.copy()]

        # Follow the reference trajectory
        for i in range(len(ref_trajectory) - self.horizon):
            ref_segment = ref_trajectory[i:i + self.horizon]
            control_input = self.optimize_control(current_state, ref_segment)
            current_state = self.apply_control(current_state, control_input)
            trajectory.append(current_state)

            # Stop if close enough to the goal
            if np.linalg.norm(current_state[:2] - ref_trajectory[-1][:2]) < 2.0:
                print("Reached near the goal")
                break

            # Plot current state
            plt.plot(current_state[0], current_state[1], "xr")
            plt.pause(0.001)

        return np.array(trajectory)


def main(map_type="ComplexGridMap"):
    # 사용자가 선택한 맵 클래스에 따라 인스턴스 생성
    if map_type == "ParkingLot":
        map_instance = ParkingLot(lot_width=100, lot_height=75)
    else:  # Default to ComplexGridMap
        map_instance = ComplexGridMap(lot_width=100, lot_height=75)

    # 유효한 시작과 목표 좌표 설정
    start_pose = map_instance.get_random_valid_start_position()
    goal_pose = map_instance.get_random_valid_goal_position()
    print(f"Start MPC Controller (start {start_pose.x, start_pose.y}, end {goal_pose.x, goal_pose.y})")

    # 맵과 장애물 및 시작/목표 지점을 표시
    map_instance.plot_map()
    plt.plot(start_pose.x, start_pose.y, "og")
    plt.plot(goal_pose.x, goal_pose.y, "xb")
    plt.xlim(-1, map_instance.lot_width + 1)
    plt.ylim(-1, map_instance.lot_height + 1)
    plt.title("MPC Route Planner")
    plt.xlabel("X [m]")
    plt.ylabel("Y [m]")
    plt.grid(True)
    plt.axis("equal")

    # Create Informed TRRT* planner
    informed_rrt_star = InformedTRRTStar(start_pose, goal_pose, map_instance, show_eclipse=False)
    
    # Ensure the route generation is completed
    try:
        rx, ry, rx_opt, ry_opt = informed_rrt_star.search_route(show_process=False)
        if len(rx_opt) == 0 or len(ry_opt) == 0:
            print("TRRT* was unable to generate a valid path.")
            return

    except Exception as e:
        print(f"Error in route generation: {e}")
        return

    # Transform reference trajectory
    ref_trajectory = transform_arrays_with_angles(rx_opt, ry_opt)

    # Plot Theta* Path
    plt.plot(rx, ry, "g--", label="Theta* Path")  # Green dashed line

    # Plot Optimized Path
    plt.plot(rx_opt, ry_opt, "-r", label="Informed TRRT* Path")  # Red solid line

    # MPC Controller
    wheelbase = 2.5  # Example wheelbase of the vehicle in meters
    mpc_controller = MPCController(horizon=10, dt=0.1, map_instance=map_instance, wheelbase=wheelbase)

    # Follow the trajectory using the MPC controller
    trajectory = mpc_controller.follow_trajectory(start_pose, ref_trajectory)
    
    plt.plot(trajectory[:, 0], trajectory[:, 1], "b-", label="MPC Path")
    plt.legend()
    plt.show()

if __name__ == "__main__":
    main()
