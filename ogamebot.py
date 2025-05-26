#!/bin/python

import sys
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import json

#local import

if len(sys.argv) > 1:
    acc = sys.argv[1]
else:
    acc = "default"

with open("accounts/" + acc + ".json", "r") as file:
    cfg = json.load(file)
    url = cfg['url']

with open("buildingsinfo.json", "r") as file:
    build_info = json.load(file)

delay = 2
planets = []
orders = []
for planet_id in cfg['planets']:
    planets.append(url + cfg['planets'][planet_id]['set_url'])
    orders.append([])

session = requests.session()
if cfg['cookie'] != '':
    session.cookies.set('PHPSESSID', cfg['cookie'])

#1: Metal #2: Crystal #3: Deut #4: Solar
ressource = ['Metal', 'Crystal', 'Deuterium']


#logs in if necessary
def check_login():
    if session.get(url + 'game.php').url == url:
        login = {\
            'kid': '',\
            'uni': '0',\
            'login': cfg['login'],\
            'pass': cfg['pass']}
        time.sleep(1)
        result = session.post(url + 'index.php', data=login)
        print('login:', result)
    

#returns the empire site as a dictionary
def get_empire_info():
    check_login()
    time.sleep(1)
    page = session.get(url + 'game.php?page=empire')
    soup = BeautifulSoup(page.content, "html.parser")
    rows = soup.find(id='content').find('table').find_all('tr')
    info = {} 
    for row in rows:
        cols = row.find_all('th')
        cols = [ele.get_text().replace('.','').strip() for ele in cols]
        if not cols: continue
        match cols[0]:
            case "Planet": info[cols[0]] = cols[1:]
            case "Name": info[cols[0]] = cols[1:]
            case "Coords": info[cols[0]] = cols[1:]
            case "Fields": info[cols[0]] = cols[1:]
            case "Metal": info[cols[0]] =\
                [[int(mp) for mp in plan.split("/")] for plan in cols[1:]]
            case "Crystal": info[cols[0]] =\
                [[int(cp) for cp in plan.split("/")] for plan in cols[1:]]
            case "Deuterium": info[cols[0]] =\
                [[int(dp) for dp in plan.split("/")] for plan in cols[1:]]
            case "Energy": info[cols[0]] =\
                [[int(ep) for ep in plan.split("/")] for plan in cols[1:]]
            case _: info[cols[0]] = [int(lvl) for lvl in cols[1:]]

    return info

#returns seconds to next event and building completion
def get_times():
    check_login()
    time.sleep(1)
    session.get(planets[0])
    time.sleep(1)
    page = session.get(url + 'game.php?page=overview')
    soup = BeautifulSoup(page.content, "html.parser")
    rows = soup.find(id='content').find('table').find_all('tr')
    overview = {} 
    for row in rows:
        cols = row.find_all('th')
        cols = [ele.get_text().strip() for ele in cols]
        if not cols: continue
        overview[cols[0]] = cols[1:]

    events = [key for key in overview.keys() if key.startswith('-\n')]
    now = datetime.strptime(overview['Server time'][0], "%d.%m.%Y %H:%M:%S")
    next_event = 9999999
    if events:
        next_event = (datetime.strptime(events[0], "-\n%d.%m.%Y %H:%M:%S") -now).seconds 

    times = []
    for p in cfg["planets"]:
        if p == "0":
            p = int(p)
        else:
            p = int(p)+1
        if 'Free' not in overview[''][p]:
            build_t = overview[''][p].split(")")[1].replace("(","").split(" ")
            t = timedelta()
            if build_t:
                t += timedelta(seconds=int(build_t.pop()[:-1]))
            if build_t:
                t += timedelta(minutes=int(build_t.pop()[:-1]))
            if build_t:
                t += timedelta(hours=int(build_t.pop()[:-1]))
            times.append(t.seconds)
        else:
            times.append(0)
            
    return (next_event, times)


#returns the cost of a building upgrade
def get_cost(building, lvl):
    b_id = build_info['id'][building]
    basecost = build_info['cost'][str(b_id)]
    cost = [(res*basecost[-1]**lvl) for res in basecost[:-1]]
    return cost


#check if all needed ressources have enough storage for order and order storage if needed
def enough_storage(planet, cost, info):
    if cost[0] > build_info['storage'][str(info['Metal Storage'][planet])]:
        print("Planning: Metal Storage @ Planet", planet)
        orders[planet].append("Metal Storage")
        return False
    if cost[1] > build_info['storage'][str(info['Crystal Storage'][planet])]:
        print("Planning: Crystal Storage @ Planet", planet)
        orders[planet].append("Crystal Storage")
        return False
    if cost[2] > build_info['storage'][str(info['Deuterium Tank'][planet])]:
        print("Planning: Deuterium Tank @ Planet", planet)
        orders[planet].append("Deuterium Tank")
        return False

    return True
    

#returns True if a order was added to orders otherwise returns False
def get_new_order(planet, info):
    if info["Energy"][planet][0] < 0 and info["Solar Plant"][planet] < cfg['planets'][str(planet)]['buildings']['Solar Plant']:
        if enough_storage(planet, get_cost("Solar Plant", info['Solar Plant'][planet]), info):
            print("Planning: Solar Plant @ Planet", planet)
            orders[planet].append("Solar Plant")
        return True

    bmax = ""
    dmax = 0
    for building, target_lvl in cfg['planets'][str(planet)]['buildings'].items():
        match building:
            case "Solar Plant": pass
            case "Metal Storage": pass
            case "Crystal Storage": pass
            case "Deuterium Tank": pass
            case "Robotics Factory": 
                dlvl = target_lvl - info[building][planet]
                if 0 < dlvl:
                    bmax = building
                    break
            case _:
                dlvl = target_lvl - info[building][planet]
                if dmax < dlvl:
                    dmax = dlvl
                    bmax = building

    if bmax: 
        if enough_storage(planet, get_cost(bmax, info[bmax][planet]), info):
            print("Planning:", bmax, info[bmax][planet]+1, "@ Planet", planet)
            orders[planet].append(bmax)
        return True
    else:
        print("Completed: Planet", planet)
        return False


#Main Loop
exp_not_tried = True
running = True
while running: 
    running = False
    info = get_empire_info()
    events = get_times()
    wait = []
    for planet in cfg['planets']:
        planet = int(planet)
#Check if planet is building
        if events[1][planet] > 0:
            wait.append(events[1][planet])
            running = True
            continue
#Check if no orders
        if not orders[planet]:
            if not get_new_order(planet, info):
                wait.append(9999999)
                continue
        running = True

        b_order = orders[planet][0]
        cost = get_cost(b_order, info[b_order][planet])
        dt = []
        for i, res in enumerate(ressource):
            diff = cost[i] - info[res][planet][0]
            if info[res][planet][1] > 0:
                dt.append(int(3600 * diff / info[res][planet][1])+delay)
            else:
                dt.append(int(3600 * diff / 1)+delay)

        dt = max(dt)
        if dt > 0:
            print("Enough for", b_order, info[b_order][planet]+1, "@ Planet", planet, "in", timedelta(seconds=dt), "@", datetime.now()+timedelta(seconds=dt))
        wait.append(max(dt, events[1][planet]))
        if dt <= 0 and events[1][planet] <= 0: 
#Run Command
            time.sleep(delay)
            print("Build:", b_order, info[b_order][planet]+1, "@ Planet", planet, datetime.now())
            check_login
            time.sleep(1)
            session.get(planets[planet])
            time.sleep(1)
            session.get(url +\
                build_info['url'][b_order] +\
                str(build_info['id'][b_order]))
            del orders[planet][0]
            break

    else:
        if wait:
            wait = min(min(wait), events[0])
            print("Waiting till", datetime.now()+timedelta(seconds=wait),\
                "for", timedelta(seconds=wait))
        else:
            running = False

        if wait == 9999999: 
            running = False
        else: 
            time.sleep(wait+delay)


info = get_empire_info()
print(info)
