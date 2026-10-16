import math
R = 6371008.8

def haversine_m(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

def bearing_deg(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2-lon1)
    y = math.sin(dl)*math.cos(p2)
    x = math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360

def elevation_deg(camera_alt, target_alt, horizontal_m):
    return math.degrees(math.atan2(target_alt-camera_alt, max(horizontal_m, 1e-6)))

def destination(lat, lon, distance_m, bearing):
    p, l, b = map(math.radians, [lat, lon, bearing])
    d = distance_m/R
    p2 = math.asin(math.sin(p)*math.cos(d)+math.cos(p)*math.sin(d)*math.cos(b))
    l2 = l+math.atan2(math.sin(b)*math.sin(d)*math.cos(p),
                      math.cos(d)-math.sin(p)*math.sin(p2))
    return math.degrees(p2), ((math.degrees(l2)+540)%360)-180
