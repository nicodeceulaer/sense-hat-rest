#!/usr/bin/env python

import web, json, rrdtool, tempfile, time, threading, os
from sense_hat import SenseHat, ACTION_HELD

sense = SenseHat()

# OPTIONAL: clean shutdown when joystick held down
def pushed_middle(event):
    if event.action == ACTION_HELD:
    	sense.clear(255, 0, 0) 
    	time.sleep(1)
    	sense.clear()
        os.system('poweroff')
sense.stick.direction_middle = pushed_middle

# get sensor data
def get_sensor(sensor):
	data = {}
	
	if sensor == 'humidity':
		data[sensor] = sense.humidity
	elif sensor == 'temperature':
		data[sensor] = sense.temperature
	elif sensor == 'temperature_from_humidity':
		data[sensor] = sense.get_temperature_from_humidity()
	elif sensor == 'temperature_from_pressure':
		data[sensor] = sense.get_temperature_from_pressure()
	elif sensor == 'pressure':
		data[sensor] = sense.pressure
	elif sensor == 'orientation_radians':
		data[sensor] = sense.orientation_radians
	elif sensor == 'orientation_degrees':
		data[sensor] = sense.get_orientation_degrees()
	elif sensor == 'orientation':
		data[sensor] = sense.orientation
	elif sensor == 'compass':
		data[sensor] = sense.compass
	elif sensor == 'compass_raw':
		data[sensor] = sense.compass_raw
	elif sensor == 'gyroscope':
		data[sensor] = sense.gyroscope
	elif sensor == 'gyroscope_raw':
		data[sensor] = sense.gyroscope_raw
	elif sensor == 'accelerometer':
		data[sensor] = sense.accelerometer
	elif sensor == 'accelerometer_raw':
		data[sensor] = sense.accelerometer_raw
		
	sense.set_imu_config(True, True, True)
			
	return data	

# rrdtool data gather thread
RRDSENSORS = ['humidity', 'temperature', 'pressure', 'compass']
def rrdthread(database, step):
	while True:
		template = ''
		data = 'N:'
		for i in RRDSENSORS:
			sensor = get_sensor(i)
			data += '%s:' % sensor[i]
			template += '%s:' %i
		data = data[:-1] #remove last ':'
		template = template[:-1]
		args = ['--template']
		args += [template, data]
		rrdtool.update(database, args);
		time.sleep(step)

# initialize database	
STEP=60 # number of seconds between each data point
DBFILE = '/var/tmp/sense-hat.rrd'
DBDAYS=365 # number of days to retain data			
if not (os.path.exists(DBFILE)):
	args = ["--start", "N", "--step", "%s" % STEP, "DS:humidity:GAUGE:%s:0:100" % (STEP*2), "DS:temperature:GAUGE:%s:-100:100" % (STEP*2), "DS:pressure:GAUGE:%s:850:1100" % (STEP*2), "DS:compass:GAUGE:%s:0:360" % (STEP*2), "RRA:MAX:0.5:1:%s" %(int(60/STEP*60*24*DBDAYS))]
    	print 'Creating database %s with args %s' %(DBFILE, args)
    	rrdtool.create(DBFILE, args)

# start sensor data gather thread
thread = threading.Thread(target=rrdthread, args=[DBFILE, STEP])
thread.start()

LIVESENSORS = RRDSENSORS + ['temperature_from_humidity', 'temperature_from_pressure', 'orientation_radians', 'orientation_degrees', 'orientation', 'compass_raw', 'gyroscope', 'gyroscope_raw', 'accelerometer', 'accelerometer_raw']
PASTSENSORS = RRDSENSORS + ['all']
IMAGES = RRDSENSORS
HTML = PASTSENSORS

# web api
urls = (
	'/live/(.*)', 'get_live',
	'/past/(.*)', 'get_past',
	'/image/(.*)', 'get_image',
	'/html/(.*)', 'get_html',
	'/', 'get_index'
)

app = web.application(urls, globals())

# returns json of live sensor data
class get_live:
    def GET(self, action):
	data = {}
	
	if action in LIVESENSORS:
		data = get_sensor(action)
	else:
		raise web.notfound()
		
	web.header('Content-Type', 'application/json')

	return json.dumps(data)
	
# returns json of past sensor data
class get_past:
    def GET(self, action):
	input = web.input(start='1h') # defaults
    	start = str(input.start)
    	sensor = str(action)
	args = [ "--start", "-%s" %start, "--json"]
	if action in RRDSENSORS:
		elements = ["DEF:%s=%s:%s:MAX" % (sensor, DBFILE, sensor), "XPORT:%s:%s" % (sensor, sensor)]
	elif action == 'all':
		elements = []
		for i in RRDSENSORS:
			elements += ["DEF:%s=%s:%s:MAX" % (i, DBFILE, i), "XPORT:%s:%s" % (i, i)]
	else:
		raise web.notfound()

	data = rrdtool.xport(elements, args)
	
	web.header('Content-Type', 'application/json')

	return json.dumps(data)

# returns a image of sensor over time
class get_image:
    def GET(self, action):
    
	WATERMARK='Sense HAT Raspberry Pi'
	HUMIDDEF='DEF:humidity=%s:humidity:MAX' %DBFILE
	HUMIDVDEF='VDEF:date=humidity,LAST'
	HUMIDLINE='LINE2:humidity#0000FF:humidity'
	HUMIDGPRINT='GPRINT:humidity:LAST:Current\: %.1lf'
	CELSIUSDEF='DEF:celsius=%s:temperature:MAX' %DBFILE
	CELSIUSLINE='LINE2:celsius#FF0000:celsius'
	CELSIUSGPRINT='GPRINT:celsius:LAST:Current\: %.1lf'
	#FAHRCDEF='CDEF:fahr=9,5,/,celsius,*,32,+' # true conversion of C to F
	FAHRCDEF='CDEF:fahr=9,5,/,celsius,*,0,+' # calibrated for radiant circuit board heat
	FAHRVDEF='VDEF:date=fahr,LAST'
	FAHRLINE='LINE2:fahr#FFA500:fahrenheit'
	FAHRGPRINT='GPRINT:fahr:LAST:Current\: %.1lf'
	PRESDEF='DEF:pressure=%s:pressure:MAX' %DBFILE
	PRESVDEF='VDEF:date=pressure,LAST'	
	PRESLINE='LINE2:pressure#00FF00:pressure'
	PRESGPRINT='GPRINT:pressure:LAST:Current\: %.1lf'
	COMPDEF='DEF:compass=%s:compass:MAX' %DBFILE
	COMPVDEF='VDEF:date=compass,LAST'
	COMPLINE='LINE2:compass#FFFF00:compass'
	COMPGPRINT='GPRINT:compass:LAST:Current\: %.1lf'
	DATEGPRINT='GPRINT:date:%F %R:strftime'

    	input = web.input(start='1h',width=600,height=400) # defaults
    	start = str(input.start)
    	width = str(input.width)
    	height = str(input.height)
    	sensor = str(action)

	args = [ "--start", "-%s" %start, "--width", "%s" %width, "--height", "%s" %height, "--title", "%s" %sensor, "--watermark", "%s" %WATERMARK]
	if action == 'humidity':
		args += ["--vertical-label", "percent", "%s" %HUMIDDEF, "%s" %HUMIDVDEF, "%s" %HUMIDLINE, "%s" %HUMIDGPRINT]
	elif action == 'temperature':
		args += ["--vertical-label", "degrees", "%s" %CELSIUSDEF, "%s" %FAHRCDEF, "%s" %FAHRVDEF, "%s" %FAHRLINE, "%s" %FAHRGPRINT]
	elif action == 'pressure':
		args += ["--vertical-label", "millibars", "--upper-limit", "1100", "--lower-limit", "850", "%s" %PRESDEF, "%s" %PRESVDEF, "%s" %PRESLINE, "%s" %PRESGPRINT]
	elif action == 'compass':
		args += ["--vertical-label", "degrees", "%s" %COMPDEF, "%s" %COMPVDEF, "%s" %COMPLINE, "%s" %COMPGPRINT]
	else:
		raise web.notfound()

	args += ["%s" %DATEGPRINT]

	fp = tempfile.NamedTemporaryFile()
	fname = str(fp.name)

	rrdtool.graph(fname, args)
	
	web.header("Content-Type", "image/png")
   
	return open(fname, "rb").read()
	
# returns html of images
class get_html:
    def GET(self, action):
        input = web.input(start='1d',width=600,height=400) # defaults
    	start = str(input.start)
    	width = str(input.width)
    	height = str(input.height)
    	sensor = str(action)
    	query = '?start=%s&width=%s&height=%s' %(start, width, height)
    	
    	data = '<html><head><meta http-equiv="refresh" content="%s"><title>%s</title></head>' % (STEP, sensor)
    	if action in IMAGES:
    		image = '/image/%s%s' %(sensor, query)
		data += '<a href="%s"><img src="%s"/></a>' % (image, image)
	elif action == 'all':
		for i in IMAGES:
			image = '/image/%s%s' %(i, query)
			data += '<a href="%s"><img src="%s"/></a>' % (image, image)
	else:
		raise web.notfound()
    	data += '</html>'
    	
	web.header("Content-Type", "text/html")

	return data

# returns usage page
class get_index:
    def GET(self):
    	host = 'http://' + web.ctx.host
	TITLE = 'Sense HAT REST API'
    	PARAMS = '[?start=n[days|hours|minutes|seconds]]'
    	IMAGEPARAMS = PARAMS + '[&width=n][&height=n]'
    	
    	data = '<html><head><title>%s</title></head>' %TITLE
    	data += '<h1>%s</h1>' %TITLE
    	data += '<h2>Live sensor json</h2>'
    	url = '%s/live/' %host
    	data += '<p>%s[' %url
	for i in LIVESENSORS:
		data += '<a href="%s%s" target="_blank">%s</a>|' % (url, i, i)
	data = data[:-1] #remove last '|'
	data += ']</p>'
	
	data += '<br><h2>Past sensor json</h2>'
	url = '%s/past/' %host
    	data += '<p>%s[' %url
	for i in PASTSENSORS:
		data += '<a href="%s%s" target="_blank">%s</a>|' % (url, i, i)
	data = data[:-1] #remove last '|'
	data += ']%s</p>' %PARAMS
	
    	data += '<br><h2>Past sensor images</h2>'
	url = '%s/image/' %host
    	data += '<p>%s[' %url
	for i in IMAGES:
		data += '<a href="%s%s" target="_blank">%s</a>|' % (url, i, i)
	data = data[:-1] #remove last '|'
	data += ']%s</p>' %IMAGEPARAMS

    	data += '<br><h2>Past sensor html</h2>'
	url = '%s/html/' %host
    	data += '<p>%s[' %url
	for i in HTML:
		data += '<a href="%s%s" target="_blank">%s</a>|' % (url, i, i)
	data = data[:-1] #remove last '|'
	data += ']%s</p>' %IMAGEPARAMS
    	
    	data += '</html>'
	
	web.header("Content-Type", "text/html")
   
	return data
	
# start the web server
if __name__ == "__main__":
    app.run()