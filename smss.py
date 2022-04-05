from bs4 import BeautifulSoup 
from colorama import init
from copy import deepcopy
from datetime import date, datetime
from glob import glob
from pathlib import Path
from random import randint
from urllib import request
import asyncio
import fileinput
import itertools
import json
import logging
import math
import os
import requests
import shutil
import sqlite3
import sys
import threading
import time
import zipfile

sys.path.insert(0, '')
init(convert=True)

class SmssConfig:
    """
    The Simplified Miscreated Server Setup class installs and configures a
    Miscreated server. Configuration customization may be carried out through
    the use of a smss.json configuration file.
    """
    def __init__(self, **kwargs):
        logging.debug("Initializing MiscreatedRCON object")
        logging.debug(f"kwargs: {kwargs}")
        
        self.config = kwargs

        # Grab some variables for the "database tricks"
        self.reset_base_clan_ids = self.config.get("reset_base_clan_ids", [])
        self.reset_base_owner_ids = self.config.get("reset_base_owner_ids", [])
        self.reset_tent_clan_ids = self.config.get("reset_tent_clan_ids", [])
        self.reset_tent_owner_ids = self.config.get("reset_tent_owner_ids", [])
        self.reset_vehicle_clan_ids = self.config.get("reset_vehicle_clan_ids", [])
        self.reset_vehicle_owner_ids = self.config.get("reset_vehicle_owner_ids", [])

        # Create a random server service ID
        this_random_number = str(randint(0, 999999)).rjust(6, "0")
        self.config["nt_service_name"] = self.config.get("nt_service_name", f'MiscreatedService{this_random_number}')
       
        # Configure paths variables for required directories and binaries
        self.script_path = os.path.dirname(os.path.realpath(__file__))
        this_path = f"{self.script_path}/MiscreatedServer"
        self.miscreated_server_path = Path(this_path)
        
        # SteamCMD installation directory
        self.steamcmd_path = Path(f"{self.script_path}/SteamCMD")

        # A place where we'll store temporary files
        self.temp_path = Path(f"{self.script_path}/temp")
        
        # Create required paths
        self.create_required_paths()

        # Configure filename variables
        self.config_file = kwargs.get('config_file', Path(f'{self.script_path}/smss.json'))
        self.miscreated_server_cmd = Path(f"{self.miscreated_server_path}/Bin64_dedicated/MiscreatedServer.exe")
        self.miscreated_server_config = Path(f"{self.miscreated_server_path}/hosting.cfg")
        self.miscreated_server_db = Path(f"{self.miscreated_server_path}/miscreated.db")
        self.steamcmd = Path(f"{self.steamcmd_path}/steamcmd.exe")

        # Variable contianing hosting.cfg contents
        self.sv_maxuptime_range = self.config.get("sv_maxuptime_range", dict())
        self.hosting_config = self.get_hosting_cvars()

        # Get our admin IDs
        self.admin_ids = self.config.get("admin_ids", list())
        self.setup_admin()
        
        # Mod handling
        self.hosting_config['steam_ugc'], self.mod_ids = self.mod_handler()

        # server commandline settings
        self.command_line_settings = dict()
        self.command_line_settings['sv_servername'] = self.hosting_config.get('sv_servername', False)


    async def run(self, cmd):
        """Leverage asyncio to execute commands

        Args:
            cmd (string): preformatted commandline command to be executed
        """
        logging.debug('async method: run')
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()

        logging.debug(f'[{cmd!r} exited with {proc.returncode}]')
        if stdout:
            logging.debug(f'[stdout]\n{stdout.decode()}')
        if stderr:
            logging.debug(f'[stderr]\n{stderr.decode()}')
        

    def add_clan_members_for_timer_resets(self):
        """Adds clan members to base, tent, and vehicle exclusion lists
        """
        logging.debug('method: add_clan_members_for_timer_resets')
        if self.reset_base_clan_ids:
            for steam_id in self.get_clan_members(self.reset_base_clan_ids):
                self.reset_base_owner_ids.append(steam_id)

        if self.reset_tent_clan_ids:
            for steam_id in self.get_clan_members(self.reset_tent_clan_ids):
                self.reset_tent_owner_ids.append(steam_id)

        if self.reset_vehicle_clan_ids:
            for steam_id in self.get_clan_members(self.reset_vehicle_clan_ids):
                self.reset_vehicle_owner_ids.append(steam_id)
    
                
    def calc_distance(self, x1, y1, x2, y2):
        """Calculates the distance between two objects on a plane

        Args:
            x1 (float): X position value for object 1
            y1 (float): Y position value for object 1
            x2 (float): X position value for object 2
            y2 (float): Y position value for object 2

        Returns:
            float: [description]
        """
        dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        return dist
    
            
    def create_required_paths(self):
        self.miscreated_server_path.mkdir(parents=True, exist_ok=True)
        self.steamcmd_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        
    def database_tricks(self):
        """Method used to bundle other methods which massage the database
        """
        logging.debug('method: database_tricks')
        # Exit this method if the server dabase does not yet exist:
        if not os.path.exists(self.miscreated_server_db):
            return
        
        self.grant_guides_in_db()
        self.add_clan_members_for_timer_resets()
        self.reset_base_timers()
        self.reset_tent_timers()
        self.quick_vehicle_despawn()
        self.reset_vehicle_timers()
        

    def get_bases_sql(self):
        """SQL command to look up all bases

        Returns:
            string: SQL command
        """
        sql = """
            SELECT (AccountID + 76561197960265728) AS Owner,
                ROUND(PosX,5) AS PosX,
                ROUND(PosY,5) AS PosY
            FROM Structures
            WHERE ClassName='PlotSign'
            """
        return sql


    def get_clan_members(self, clan_ids):
        """Query the database for members of a clan

        Returns:
            list: clan member ids
        """
        logging.debug('method: get_clan_members')
        sql = """SELECT (AccountID + 76561197960265728) AS SteamID
                 FROM ClanMembers WHERE ClanID IN ({})"""
        sql = sql.format(', '.join(str(t) for t in clan_ids))
        result = self.get_result_set(sql)
        member_ids = list()
        for record in result:
            member_ids.append(record[0])
        return member_ids

        
    def get_hosting_cvars(self):
        hosting_cfg = deepcopy(self.config.get("cvars", {}))
        sv_motd = str(hosting_cfg.get('sv_motd', False))
        sv_url = str(hosting_cfg.get('sv_url', False))
        hosting_cfg['http_password'] = str(hosting_cfg.get('http_password', 'secret{}'.format(str(randint(0, 99999)).rjust(5, "0"))))
        hosting_cfg['sv_servername'] = str(hosting_cfg.get('sv_servername', 'Miscreated Self-hosted Server #{}'.format(str(randint(0, 999999)).rjust(6, "0"))))
        if sv_motd:
            hosting_cfg['sv_motd'] = sv_motd
        if sv_url:
            hosting_cfg['sv_url'] = sv_url
        override_sv_maxuptime = self.override_sv_maxuptime()
        logging.debug(f'sv_maxuptime: {override_sv_maxuptime}')
        if override_sv_maxuptime:
            hosting_cfg['sv_maxuptime'] = override_sv_maxuptime
        logging.debug(hosting_cfg)
        return hosting_cfg


    def get_mod_name(self, mod_id):
        """Retrieves the name of a Steam Workshop mod

        Args:
            mod_id (int): Steam Workshop file id

        Returns:
            string: Steam Workshop mod name
        """
        url="https://steamcommunity.com/sharedfiles/filedetails/?id={}".format(mod_id)
        try:
            reqs = requests.get(url)
            soup = BeautifulSoup(reqs.text, 'html.parser')
            title = soup.find('title').get_text()
        except Exception as e:
            return mod_id
        if title.find("Steam Workshop::") >= 0:
            title = title.replace("Steam Workshop::",mod_id + ": ")
        else:
            title = mod_id
        return title


    def get_mod_titles(self):
        """Returns a list of mod ids and their names, formatted for output in
           the server start summary screen.

        Returns:
            string: list of mod ids and their names
        """
        int_mod_ids = list()
        for mod in self.mod_ids:
            try:
                int_mod_ids.append(int(mod))
            except:
                continue

        if not len(int_mod_ids):
            return "<none>"

        first = True
        mod_list = ''
        for mod in self.mod_ids:
            this_line = ''
            if not first:
                this_line = '\n'+' '*20
            mod_list = mod_list + this_line + self.get_mod_name(mod)
            first=False
        return mod_list


    def get_result_set(self, sql):
        """The executes a passed SQL command and returns a result set. If
           INSERT or UPDATE is detected, a write is assumed and a commit is
           also performed.

        Args:
            sql (string): SQL command

        Returns:
            list: a result set resulting from the execution of the SQL command
        """
        if not os.path.exists(self.miscreated_server_db):
            logging.debug('Database not yet created')
            return False

        logging.debug(sql)

        # If 'insert ' or 'update ' exist in the sql statement, we're probably
        # doing a database write and will want to commit the changes.
        commit = (sql.lower().find('insert ') >= 0) or \
                 (sql.lower().find('update ') >= 0)

        conn = sqlite3.connect(self.miscreated_server_db)
        c = conn.cursor()
        try:
            results = c.execute(sql)
            if commit:
                conn.commit()
        except sqlite3.Error as e:
            print(e)
            return None
        result_set = list()
        for result in results.fetchall():
            result_set.append(result)

        return result_set


    def get_server_build_id(self):
        result = requests.get('https://api.steamcmd.net/v1/info/302200')
        if result.status_code != 200:
            return -1
        app_info = json.loads(result.text)
        build_id = app_info.get('data', {}).get('302200', {}).get('depots', {}).get('branches', {}).get('public', {}).get('buildid', -1)
        return build_id


    def get_server_id_from_db(self):
        """Attempts to lookup an existing server ID from the Miscreated
           database, returning the first identified server ID or 100.

        Returns:
            int: Server ID of the Miscreated game server
        """
        logging.debug('method: get_server_id_from_db')
        if not os.path.exists(self.miscreated_server_db):
            logging.debug('Database not yet created')
            logging.debug('Using default database ID')
            return 100
        logging.debug('Retrieving first server ID found in the database')
        query = 'SELECT GameServerID FROM Characters ORDER BY CharacterID LIMIT 1'
        try:
            conn = sqlite3.connect(self.miscreated_server_db)
            cur = conn.cursor()
            cur.execute(query)
            record = cur.fetchone()
            result = record[0]
        except Exception as e:
            logging.debug('Error retrieving first server ID found in the database')
            logging.debug(e)
            logging.debug('Falling back to default server ID of 100')
            result = 100
        return result


    def get_start_server_message(self):
        """Returns a block of text to be used for the server start summary
           screen

        Returns:
            string: server summary string
        """

        # The following is just some ASCII characters for creating boxes
        # ║╔╗╚╝─═╟╢
        
        message = '═'*118+'\r\n'+'═'*118+'\r\n'\
                  '       [1m[36mServer Name: [1m[33m{sv_servername}[0m\r\n'\
                  '               [1m[36mMap: [1m[33m{map}[0m\r\n'\
                  '              [1m[36mMods: [1m[33m{mods}[0m\r\n'\
                  '  [1m[36mGame Ports (UDP): [1m[33m{port}[0m\r\n'\
                  '   [1m[36mRCON Port (TCP): [1m[33m{rcon}[0m\r\n'\
                  ''+'═'*78+'\r\n\r\n'\
                  'Launching Miscreated server process ({timestamp})...\r\n'\
                  '╔'+'═'*76+'╗\r\n'\
                  '║'+' '*26+'[1m[31mDO NOT CLOSE THIS WINDOW[0m'+' '*26+'║\r\n'\
                  '║'+' '*76+'║\r\n'\
                  '╟'+'─'*76+'╢\r\n'\
                  '║'+' '*76+'║\r\n'\
                  '║  This window maintains the Miscreated server. If this window is closed     ║\r\n'\
                  '║  the server will not automatically restart.'+' '*32+'║\r\n'\
                  '║'+' '*76+'║\r\n'\
                  '╚'+'═'*76+'╝'
        return message


    def get_steam(self):
        """Ensures steamcmd.exe is installed
        """
        logging.debug('method: get_steam')
        if os.path.exists(self.steamcmd):
            logging.debug("{} exists. Skipping download.".format(self.steamcmd))
            return

        logging.info("{} does not exist".format(self.steamcmd))
        steamcmd_url = 'https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip'
        steamcmd_zip_file = Path("{}/steamcmd.zip".format(self.temp_path))

        try:
            logging.info("Attempting SteamCMD download")
            request.urlretrieve(steamcmd_url, steamcmd_zip_file)
        except Exception as e:
            logging.debug(e)

        try:
            logging.info("Extracting {} archive".format(steamcmd_zip_file))
            with zipfile.ZipFile(steamcmd_zip_file, 'r') as zip_ref:
                zip_ref.extractall(self.steamcmd_path)
        except Exception as e:
            logging.debug(e)


    def get_tents_sql(self):
        """SQL command to look up all tents

        Returns:
            string: SQL command
        """
        sql = """
            SELECT StructureID,
                ROUND(PosX,5) AS PosX,
                ROUND(PosY,5) AS PosY
            FROM Structures
            WHERE ClassName like '%tent%'
            """
        return sql


    def get_vehicles_sql(self):
        """SQL command to look up all vehicles

        Returns:
            string: SQL command
        """
        sql = """
            SELECT VehicleID,
                ROUND(PosX,5) AS PosX,
                ROUND(PosY,5) AS PosY
            FROM Vehicles
            """
        return sql


    def grant_guides_in_db(self):
        """Grants all guides to players.
        """
        logging.debug('method: grant_guides_in_db')
        if not self.config.get('grant_guides', False):
            return

        logging.debug('Granting guides to all players')

        sql = """
        DROP TRIGGER IF EXISTS grant_all_guides;
        CREATE TRIGGER IF NOT EXISTS grant_all_guides AFTER UPDATE ON Characters BEGIN UPDATE ServerAccountData SET Guide00="-1", Guide01="-1"; END; UPDATE ServerAccountData SET Guide00="-1", Guide01="-1";
        """
        try:
            conn = sqlite3.connect(self.miscreated_server_db)
            conn.executescript(sql)
        except Exception as e:
            logging.debug(e)


    def launch_server(self):
        """Launch a Miscreated server instance
        """
        logging.debug('method: launch_server')

        semaphore_file = Path('{}/smss.managed'.format(self.miscreated_server_path))

        f = open(semaphore_file, "w")
        f.write("This server is managed by Spafbi's Simplified Miscreated Server Setup script.")
        f.close()

        server_options = list()

        bind_ip = self.config.get('bind_ip', False)
        enable_whitelist = self.config.get('enable_whitelist', False)
        enable_rcon = self.config.get('enable_rcon', True)
        server_id = self.get_server_id_from_db()
        base_port = int(self.config.get('server_base_port', 64090))
        max_players = int(self.config.get('max_players', 36))
        miscreated_map = str(self.config.get('map', 'islands'))
        sv_servername = self.hosting_config.get('sv_servername', False)
        
        if bind_ip:
            server_options.append('-sv_bind {}'.format(str(bind_ip)))

        if enable_whitelist:
            server_options.append('-mis_whitelist')
        
        if enable_rcon:
            server_options.append('+http_startserver')

        server_options.append('-sv_port {}'.format(base_port))
        server_options.append('-mis_gameserverid {}'.format(server_id))
        server_options.append('+sv_maxplayers {}'.format(max_players))
        server_options.append('+map {}'.format(miscreated_map))
        server_options.append('+sv_servername "{}"'.format(sv_servername))

        server_options = ' '.join(str(e) for e in server_options)

        server_cmd = '"{}"'.format(self.miscreated_server_cmd) + ' ' + server_options
    
        timestamp = str(date.today()) + ', ' + str(datetime.now().strftime("%I:%M %p"))
        message = self.get_start_server_message().format(
            date=date.today(),
            map=miscreated_map,
            mods=self.get_mod_titles(),
            port=", ".join([str(i) for i in range(base_port, base_port+4)]),
            rcon=base_port+4,
            sv_servername=sv_servername,
            timestamp=timestamp)
        print(message)
        logging.debug(server_cmd)
        logging.debug('Server started: ' + timestamp)
        asyncio.run(self.run(server_cmd))
        timestamp = str(date.today()) + ', ' + str(datetime.now().strftime("%I:%M %p"))
        logging.debug('Server closed: ' + timestamp)


    def mod_handler(self):
        steam_ugc = str(self.hosting_config.get('steam_ugc', '')).replace(' ', '').replace(';', ',').replace(':', ',')
        mod_ids = list()

        # Add Theros' admin mod if there are admin ID's configured
        if len(self.admin_ids):
            steam_ugc = f"2011185435,{steam_ugc}"

        # Process user defined mods and make sure IDs are unique
        for mod in steam_ugc.split(','):
            if mod not in mod_ids:
                mod_ids.append(mod)

        mod_ids.sort()
        
        this_steam_ugc = ','.join(str(m) for m in mod_ids)
        
        return this_steam_ugc, mod_ids


    def override_sv_maxuptime(self):
        if not self.sv_maxuptime_range.get('enabled', False):
            logging.debug(f'self.sv_maxuptime_range: {self.sv_maxuptime_range}')
            return False
        
        try:
            min_val = float(self.sv_maxuptime_range.get('min', 8))
            max_val = float(self.sv_maxuptime_range.get('max', 12))
        except:
            min_val = 8
            max_val = 12

        logging.debug(f'override_sv_maxuptime min: {min_val}')
        logging.debug(f'override_sv_maxuptime max: {max_val}')

        from random import SystemRandom
        return round(SystemRandom().uniform(min_val, max_val), 1)


    def prepare_server(self):
        """Method to bundle other methods to ensure server is ready to run
        """
        logging.debug('method: prepare_server')
        self.remove_server_mods()
        self.get_steam()
        self.validate_miscreated_server()
        
        
    def remove_server_mods(self):
        """Remove the mods directory if it exists. This is done to ensure that
           the latest version of the mods are installed in the Miscreated
           directory. We do this because Steam doesn't properly validate and
           refresh the mods; this does not force the mods to redownload each
           time as they are cached by steamcmd.
        """
        logging.debug('method: remove_server_mods')
        mods_dir = Path('{}/Mods'.format(self.miscreated_server_path))
        if os.path.exists(mods_dir):
            logging.debug('Removing mods directory to refresh mods')
            try:
                shutil.rmtree(mods_dir, ignore_errors=True)
            except OSError as e:
                logging.debug("Error: {} : {}".format(mods_dir, e.strerror))


    def replace_config_lines(self, filename, variable, value):
        """This method replaces all matching lines in config files having the
           format "variable=value"

        Args:
            filename (string): filesystem path to a file
            variable (string): variable name to be added or updated with a new
                               value
            value (string): the new value for the variable
        """
        logging.debug('method: replace_config_lines :: {}'.format(variable))
        # We haven't replaced anything yet so this value is False
        replaced = False

        # This rewrites the file making subsitutions where needed
        if os.path.exists(filename):
            for line in fileinput.input([filename], inplace=True):
                if line.strip().lower().startswith('{}='.format(variable.lower())):
                    line = '{}={}\n'.format(variable, value)
                    replaced = True
                sys.stdout.write(line)

        # if no lines were replaced open the file and write out the variable/value pair
        if not replaced:
            try:
                with open(filename, 'r') as f:
                    for line in f:
                        pass
            except:
                line = ''
            file_name = open(filename, 'a+')
            if not line == "\n":
                file_name.write('\n')
            file_name.write('{}={}'.format(variable, value))
            file_name.close

                
    def reset_base_timers(self):
        """Reset base timers according to configured settings
        """
        if self.config.get('reset_all_bases', False):
            sql = "UPDATE Structures SET AbandonTimer=2419200 WHERE ClassName='PlotSign';"
            self.get_result_set(sql)
            return
        
        if not self.reset_base_owner_ids:
            return
        
        bases = self.get_result_set(self.get_bases_sql())

        account_ids = list()
        for base in bases:
            if base[0] in self.reset_base_owner_ids:
                account_ids.append(int(base[0]) - 76561197960265728)

        if len(account_ids):
            logging.debug('Reset bases for AccountIDs: {}'.format(account_ids))
            sql = "UPDATE Structures SET AbandonTimer=2419200 WHERE ClassName='PlotSign' AND AccountID IN ({});"
            sql = sql.format(', '.join(str(t) for t in account_ids))
            self.get_result_set(sql)


    def reset_base_object_timers(self, objects, owner_ids, update_sql, thing):
        """Reset timers bases on passed settings.

        Args:
            objects (dictionary): result set of objects to be reset
            owner_ids (list): 'owner' ids for which objects should be reset
            update_sql (string): SQL command to perform update
            thing (string): the type of object being reset - for logging purposes
        """
        bases = self.get_result_set(self.get_bases_sql())

        if not bases:
            return

        reset_objects = list()

        for base in bases:
            steam_id = base[0]
            x1 = base[1]
            y1 = base[2]
            if steam_id not in owner_ids:
                continue
            for this_object in objects:
                x2 = this_object[1]
                y2 = this_object[2]
                if self.calc_distance(x1, y1, x2, y2) <= 30:
                    reset_objects.append(this_object[0])

        if not len(reset_objects):
            return

        logging.debug('Reset {} ids: {}'.format(thing, reset_objects))
        update_sql = update_sql.format(', '.join(str(t) for t in reset_objects))
        self.get_result_set(update_sql)


    def reset_tent_timers(self):
        """Reset tent timers according to configured settings
        """
        if self.config.get('reset_all_tents', False):
            sql = "UPDATE Structures SET AbandonTimer=2419200 WHERE ClassName like '%tent%';"
            self.get_result_set(sql)
            return

        if not self.reset_tent_owner_ids:
            return
        
        tents = self.get_result_set(self.get_tents_sql())

        if not tents:
            return

        sql = "UPDATE Structures SET AbandonTimer=2419200 WHERE StructureID IN ({});"
        self.reset_base_object_timers(tents, self.reset_tent_owner_ids, sql, 'tent')


    def quick_vehicle_despawn(self):
        """Reset vehicle timers for quick despawns after restart
        """
        quick_vehicle_despawn = int(self.config.get('quick_vehicle_despawn', False))
        if quick_vehicle_despawn:
            sql = f"UPDATE Vehicles SET AbandonTimer={quick_vehicle_despawn};"
            self.get_result_set(sql)
            return


    def reset_vehicle_timers(self):
        """Reset vehicle timers according to configured settings
        """
        if self.config.get('reset_all_vechicles', False):
            sql = "UPDATE Vehicles SET AbandonTimer=2419200;"
            self.get_result_set(sql)
            return

        if not self.reset_vehicle_owner_ids:
            return
        
        vehicles = self.get_result_set(self.get_vehicles_sql())

        if not vehicles:
            return

        sql = "UPDATE Vehicles SET AbandonTimer=2419200 WHERE VehicleID IN ({});"
        self.reset_base_object_timers(vehicles, self.reset_vehicle_owner_ids, sql, 'vehicle')


    def setup_admin(self):
        """Updates the SvServerAdmin/settings.cfg file with the current class
           values if any ids are specified in the theros_admin_ids variable
        """
        logging.debug('method: update_admin_cfg')
        if not len(self.admin_ids):
            return
    
        # Create the mod configuration directory if it doesn't exist
        admin_config_path = Path(f"{self.miscreated_server_path}/SvServerAdmin")
        admin_config_path.mkdir(parents=True, exist_ok=True)

        # Convert the list to a string for use in the config file
        server_owner=','.join(str(t) for t in self.admin_ids)
        server_owner=f'"{server_owner}"'
        
        # Assign sever_owner as the ServerOwner value in the mod config file
        admin_config = Path(f"{admin_config_path}/settings.cfg")
        self.replace_config_lines(admin_config, 'ServerOwner', server_owner)


    def spinner(self):
        """As long as self.spinner_done is False a spinner will appear to help
           keep the script from looking like it's stalled.
        """
        for c in itertools.cycle(['|', '/', '-', '\\']):
            if self.spinner_done:
                break
            sys.stdout.write('\rloading ' + c)
            sys.stdout.flush()
            time.sleep(0.1)
        sys.stdout.write('\r')

                
    def stop_file_exists(self):
        """If any file staring with "stop" exists in the script directory then
            return True
        """
        if len(glob(str(Path(f'{self.script_path}/stop*')))):
            logging.info('stop file exists')
            return True
        return False


    def validate_miscreated_server(self):
        """Validates the Miscreated server. This also has the effect of
           installing the server if not yet installed.
        """
        logging.debug('method: validate_miscreated_server')

        installed_server_build_id = int(self.config.get("server_build_id", 0))
        current_server_build_id = int(self.get_server_build_id())
        self.config['server_build_id'] = current_server_build_id
        self.write_json_cfg()
        
        build_ids_match = (installed_server_build_id == current_server_build_id)
        miscreated_binary_exists = os.path.exists(self.miscreated_server_cmd)
        server_build_non_negative = (current_server_build_id != -1)
        
        # If the installed Miscreated server has the same build id as the steam build ID, skip this step.
        if miscreated_binary_exists and build_ids_match and server_build_non_negative:
            return

        # Create the command used to validate/install the server
        install_cmd = 'steam_cmd +login anonymous +force_install_dir miscreated_server_path '\
                      '+app_update 302200 validate +quit'
        install_cmd = install_cmd.replace('steam_cmd', str(self.steamcmd))
        install_cmd = install_cmd.replace('miscreated_server_path', str(self.miscreated_server_path))
        
        # Execute the command
        logging.info('Validating Miscreated Server installation. This could take a while...')

        self.spinner_done=False
        t = threading.Thread(target=self.spinner)
        t.start()
        asyncio.run(self.run(install_cmd))
        self.spinner_done=True
        logging.info('Miscreated Server installation validated')


    def write_hosting_cfg(self):
        """Writes the hosting.cfg file with the current class values
        """
        logging.debug('method: write_hosting_cfg')
        logging.debug(f'hosting_config: {self.hosting_config}')
        hosting_cfg = open(self.miscreated_server_config, "w")
        for key, value in self.hosting_config.items():
            if type(value) is str:
                if not len(value):
                    continue
            if type(value) is list:
                for this_val in value:
                    hosting_cfg.write(f"{key}={this_val}\n")
                continue
            if key in ('sv_servername', 'sv_motd', 'sv_url'):
                value=f"\"{value}\""
            hosting_cfg.write(f"{key}={value}\n")
        hosting_cfg.close()


    def write_json_cfg(self):
        """Writes the json config file with the current class values
        """
        logging.debug('method: write_json_cfg')
        this_config = deepcopy(self.config)
        this_config.pop('config_file')
        contents = json.dumps(this_config, indent=4)
        smss_json = open(f"{self.config_file}", "w")
        smss_json.write(contents)
        smss_json.close()


def main():
    """
    Summary: Default method if this module is run as __main__.
    """
    import argparse

    # Argeparse description and configuration
    prog = os.path.basename(__file__)
    description = "{prog} Runs a Miscreated game server - all values not "\
                  "configured in a JSON formatted file will use Miscreated "\
                  "server defaults.".format(prog=prog)
    parser = argparse.ArgumentParser(prog=prog, description=description)
    args = parser.parse_args()

    # This just grabs our script's path for reuse
    script_path = os.path.abspath(os.path.dirname(sys.argv[0]))

    # Check to see if the path includes a space and exit if it does
    if script_path.find(' ') >= 0:
        print('This script cannot be run in paths having spaces. Current path:')
        print(f'   {script_path}' + "\n")
        return

    # Check for files to trigger debug logging
    verbose = True if len(glob(str(Path(f'{script_path}/debug*')))) else False

    # Enable either INFO or DEBUG logging
    if verbose:
        smss_logger = logging.getLogger()
        smss_logger.setLevel(logging.DEBUG)

        output_file_handler = logging.FileHandler("smss.log")
        stdout_handler = logging.StreamHandler(sys.stdout)

        smss_logger.addHandler(output_file_handler)
        smss_logger.addHandler(stdout_handler)
    else:
        logging.basicConfig(level=logging.INFO)

    # Output argparse values
    logging.debug(args)

    # Read the JSON configuration file
    json_config_file = Path(f"{script_path}/smss.json")
    try:
        with open(json_config_file) as f:
            json_config = json.load(f)
    except Exception as e:
        logging.debug(e)
        logging.debug("Configuration file load error. Using default configuration")
        json_config={}

    logging.debug(json_config)
    
    json_config['config_file'] = f"{json_config_file}"

    smss = SmssConfig(**json_config)

    # Setup admin using Theros admin mod.
    smss.setup_admin()
    
    # Write hosting.cfg
    smss.write_hosting_cfg()
    exit()
    
    # Prepare the Miscreated server
    smss.prepare_server()
    
    # Execute database maintenance "tricks"
    smss.database_tricks()

    # Record the time we start the server
    start_time = time.time()

    # # Launch the Miscreated server
    smss.launch_server()

    # If the server executed prematurely sleep before exiting this script
    if time.time() - start_time < 10:
        print("The server process exited in less than 10 seconds. This script will sleep for five minutes before restarting.")
        time.sleep(300)
    

if __name__ == '__main__':
    main()