import gamelib
import random
import math
import warnings
from sys import maxsize
import json


"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips: 

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical 
  board states. Though, we recommended making a copy of the map to preserve 
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """ 
        Read in config and perform any initial setup here 
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global WALL, SUPPORT, TURRET, SCOUT, DEMOLISHER, INTERCEPTOR, MP, SP
        WALL = config["unitInformation"][0]["shorthand"]
        SUPPORT = config["unitInformation"][1]["shorthand"]
        TURRET = config["unitInformation"][2]["shorthand"]
        SCOUT = config["unitInformation"][3]["shorthand"]
        DEMOLISHER = config["unitInformation"][4]["shorthand"]
        INTERCEPTOR = config["unitInformation"][5]["shorthand"]
        MP = 1
        SP = 0
        # This is a good place to do initial setup
        self.scored_on_locations = []

    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.

        self.starter_strategy(game_state)

        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some interceptors early on.
        We will place turrets near locations the opponent managed to score on.
        For offense we will use long range demolishers if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Scouts to try and score quickly.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download
        if game_state.turn_number == 0:
            wall_locations = [[0,13],[1,13],[2,13],[2,12],[3,12],[4,11],[7,10],[8,9],[9,10],[10,9],[17,9],[18,10],[19,9],[20,10],[23,11],[24,12],[25,12],[25,13],[26,13],[27,13]]
            game_state.attempt_spawn(WALL, wall_locations)
            
        
        game_state.attempt_spawn(TURRET, [[2,11],[25,11]])
        game_state.attempt_upgrade([[2,11],[25,11]])                
        game_state.attempt_spawn(TURRET, [[9,9],[18,9]])
        
        left_tunnel = [[2,13],[2,12],[3,12],[6,10]]
        right_tunnel = [[24,12],[25,12],[25,13],[21,10]]
        if game_state.get_resource(1,0) <= 11:
            game_state.attempt_spawn(WALL, left_tunnel + right_tunnel)
        
        reinforce_location = [[0,13],[27,13],[1,12],[26,12],[4,11],[23,11]]
        mid_location = [[i,9] for i in range(11,17)]
        left_location = [[1,12],[3,13],[6,10],[4,12],[5,11]]
        right_location = [[26,12],[24,13],[21,10],[23,12],[22,11]]
        
        game_state.attempt_spawn(WALL, mid_location[1:6:2])
        for i in range(3):
            game_state.attempt_spawn(WALL, [left_location[i], right_location[i]])
        game_state.attempt_upgrade([[9,9],[18,9]])
        for x in reinforce_location:
            if game_state.contains_stationary_unit(x):
                game_state.attempt_upgrade(x)
            else:
                game_state.attempt_spawn(WALL, x)
        for i in range(3,5):
            game_state.attempt_spawn(WALL, [left_location[i], right_location[i]])
        game_state.attempt_spawn(WALL, mid_location[0:6:2])
        
        
        if game_state.project_future_MP() > 11 and game_state.get_resource(1,0) <= 11:
            game_state.attempt_remove(left_tunnel)
            game_state.attempt_remove(right_tunnel)
            
        if game_state.get_resource(1,0) > 11:
            start = self.least_damage_spawn_location(game_state, [[10,3],[11,2],[12,1],[13,0],[14,0],[15,1],[16,2],[17,3]])
            game_state.attempt_spawn(SCOUT, start, num=100)
            

        
    def enemy_least_damage_target(self, game_state):
        enemy_options = game_state.game_map.get_edge_locations(game_state.game_map.TOP_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.TOP_RIGHT)
        damages = [self.compute_damage(game_state, enemy_options[i], 1) for i in range(len(enemy_options))]
        idx = damages.index(min(damages))
        return game_state.find_path_to_edge(enemy_options[idx])[-1], damages[idx]
    
    def compute_damage(self, game_state, start_location, player_index):
        damage = 0
        path = game_state.find_path_to_edge(start_location)
        for location in path:
            damage += len(game_state.get_attackers(location, player_index)) * gamelib.GameUnit(TURRET, game_state.config).damage_i
        return damage
        

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to 
        estimate the path's damage risk.
        """
        damages = [self.compute_damage(game_state, location_options[i], 0) for i in range(len(location_options))]
        return location_options[damages.index(min(damages))]

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called 
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at in json-docs.html in the root of the Starterkit.
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly, 
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                gamelib.debug_write("All locations: {}".format(self.scored_on_locations))


if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
