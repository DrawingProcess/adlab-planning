"""
Free map (Parking Lot) Hybrid A Star Route Planner

Reference:
PythonRobotics A* grid planning (author: Atsushi Sakai(@Atsushi_twi) / Nikos Kanargias (nkana@tee.gr))
https://github.com/AtsushiSakai/PythonRobotics/blob/master/PathPlanning/AStar/a_star.py
"""

import math
import matplotlib.pyplot as plt
import argparse
import json

from utils import transform_trajectory, calculate_trajectory_distance

from map.parking_lot import ParkingLot
from map.fixed_grid_map import FixedGridMap
from map.random_grid_map import RandomGridMap

from route_planner.geometry import Pose

class Node:
    def __init__(
            self,
            pose,
            cost,
            steering,
            parent_node_index,
    ):
        self.pose = pose
        self.discrete_x = round(pose.x)
        self.discrete_y = round(pose.y)
        self.cost = cost
        self.steering = steering
        self.parent_node_index = parent_node_index


class HybridAStarRoutePlanner:
    def __init__(self, start_pose, goal_pose, map_instance):
        self.start_node = Node(start_pose, 0, 0, -1)
        self.goal_node = Node(goal_pose, 0, 0, -1)
        self.map_instance: ParkingLot = map_instance

        # Motion Model
        self.wheelbase = 2.7
        steering_degree_inputs = [-40, -20, -10, 0, 10, 20, 40]
        self.steering_inputs = [math.radians(x) for x in steering_degree_inputs]
        self.chord_lengths = [2, 1]

    def search_route(self, show_process=False):
        open_set = {self.map_instance.get_grid_index(self.start_node.discrete_x, self.start_node.discrete_y): self.start_node}
        closed_set = {}

        while open_set:
            current_node_index = min(
                open_set,
                key=lambda o: open_set[o].cost + self.calculate_heuristic_cost(open_set[o]),
            )
            current_node = open_set[current_node_index]

            if show_process:
                self.plot_process(current_node, closed_set)

            if self.calculate_distance_to_end(current_node.pose) <= 1:
                print("Find Goal")
                self.goal_node = current_node
                
                rx, ry = self.process_route(closed_set)
                route_trajectory = transform_trajectory(rx, ry)
                total_distance = calculate_trajectory_distance(route_trajectory)
                return True, total_distance, route_trajectory

            # Remove the item from the open set
            del open_set[current_node_index]

            # Add it to the closed set
            closed_set[current_node_index] = current_node

            next_nodes = [
                self.calculate_next_node(
                    current_node, current_node_index, velocity, steering
                )
                for steering in self.steering_inputs
                for velocity in self.chord_lengths
            ]
            for next_node in next_nodes:
                if self.map_instance.is_not_crossed_obstacle(
                        (current_node.discrete_x, current_node.discrete_y),
                        (next_node.discrete_x, next_node.discrete_y),
                ):
                    next_node_index = self.map_instance.get_grid_index(next_node.discrete_x, next_node.discrete_y)
                    if next_node_index in closed_set:
                        continue

                    if next_node_index not in open_set:
                        open_set[next_node_index] = next_node  # discovered a new node
                    else:
                        if open_set[next_node_index].cost > next_node.cost:
                            # This path is the best until now. record it
                            open_set[next_node_index] = next_node

        print("Cannot find Route")
        return False, 0, []

    def process_route(self, closed_set):
        rx = [self.goal_node.pose.x]
        ry = [self.goal_node.pose.y]
        parent_node = self.goal_node.parent_node_index
        while parent_node != -1:
            n = closed_set[parent_node]
            rx.append(n.pose.x)
            ry.append(n.pose.y)
            parent_node = n.parent_node_index
        rx.reverse()
        ry.reverse()
        return rx, ry

    def calculate_next_node(self, current, current_node_index, chord_length, steering):
        theta = self.change_radians_range(
            current.pose.theta + chord_length * math.tan(steering) / float(self.wheelbase)
        )
        x = current.pose.x + chord_length * math.cos(theta)
        y = current.pose.y + chord_length * math.sin(theta)

        return Node(
            Pose(x, y, theta),
            current.cost + chord_length,
            steering,
            current_node_index,
        )

    def calculate_heuristic_cost(self, node):
        distance_cost = self.calculate_distance_to_end(node.pose)
        angle_cost = abs(self.change_radians_range(node.pose.theta - self.goal_node.pose.theta)) * 0.1
        steering_cost = abs(node.steering) * 10

        cost = distance_cost + angle_cost + steering_cost
        return float(cost)

    def calculate_distance_to_end(self, pose):
        distance = math.sqrt(
            (pose.x - self.goal_node.pose.x) ** 2 + (pose.y - self.goal_node.pose.y) ** 2
        )
        return distance

    @staticmethod
    # Imitation Code: https://stackoverflow.com/a/29237626
    # Return radians range from -pi to pi
    def change_radians_range(angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    @staticmethod
    def plot_process(current_node, closed_set):
        # show graph
        plt.plot(current_node.discrete_x, current_node.discrete_y, "xc")
        # for stopping simulation with the esc key.
        plt.gcf().canvas.mpl_connect(
            "key_release_event",
            lambda event: [exit(0) if event.key == "escape" else None],
        )
        if len(closed_set.keys()) % 10 == 0:
            plt.pause(0.001)

def main():
    parser = argparse.ArgumentParser(description="Adaptive MPC Route Planner with configurable map, route planner, and controller.")
    parser.add_argument('--map', type=str, default='fixed_grid', choices=['parking_lot', 'fixed_grid', 'random_grid'], help='Choose the map type.')
    parser.add_argument('--conf', help='Path to configuration JSON file', default=None)
    args = parser.parse_args()

    if args.conf:
        # Read the JSON file and extract parameters
        with open(args.conf, 'r') as f:
            config = json.load(f)

        start_pose = Pose(config['start_pose'][0], config['start_pose'][1], config['start_pose'][2])
        goal_pose = Pose(config['goal_pose'][0], config['goal_pose'][1], config['goal_pose'][2])
        width = config.get('width', 50)
        height = config.get('height', 50)
        obstacles = config.get('obstacles', [])
    else:
        # Use default parameters
        width = 50
        height = 50
        start_pose = Pose(2, 2, 0)
        goal_pose = Pose(width - 5, height - 5, 0)
        obstacles = None  # Will trigger default obstacles in the class

    # Map selection using dictionary
    map_options = {
        'parking_lot': ParkingLot,
        'fixed_grid': FixedGridMap,
        'random_grid': RandomGridMap
    }
    map_instance = map_options[args.map](width, height, obstacles)

    if args.map == "random_grid":
        start_pose = map_instance.get_random_valid_start_position()
        goal_pose = map_instance.get_random_valid_goal_position()
    print(f"Start planning (start {start_pose.x, start_pose.y}, end {goal_pose.x, goal_pose.y})")

    map_instance.plot_map(title="Hybrid A Star Route Planner")
    plt.plot(start_pose.x, start_pose.y, "og")
    plt.plot(goal_pose.x, goal_pose.y, "xb")

    hybrid_a_star_route_planner = HybridAStarRoutePlanner(map_instance)
    isReached, total_distance, route_trajectory = hybrid_a_star_route_planner.search_route(start_pose, goal_pose, True)
    plt.plot(route_trajectory[:, 0], route_trajectory[:, 1], "-r")
    plt.pause(0.001)
    plt.show()


if __name__ == "__main__":
    main()
