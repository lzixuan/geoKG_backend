#!/usr/bin/env python
from flask import Flask, Response, request
import json
from flask_cors import CORS
from py2neo import Graph, Node, Subgraph, Relationship
from ast import literal_eval

graph = Graph("http://162.105.88.50:7474/db/data", user='neo4j', password='graphdb')
app = Flask(__name__)

topic_num = {'居民区': '1', '美食': '2', '旅游': '3', '娱乐': '4',
    '运动': '5', '酒店': '6', '学校': '7', '培训机构': '8',
    '医院': '9', '工作': '10', '购物': '11', '交通': '12',
    '生活保障': '13',}

# r'/*' 是通配符，让本服务器所有的 URL 都允许跨域请求
CORS(app, resources=r'/*')

class Place:
    def __init__(self, index, name, qu, topic, posRate, time, lat, lng):
        self.index = index
        self.name = name
        self.qu = qu
        self.topic = topic
        self.posRate = posRate
        self.time = time
        self.lat = lat
        self.lng = lng
        if len(topic) == 1:
            self.score = topic[0]
        elif len(topic) == 2:
            self.score = topic[0] + 0.75 * topic[1]
        elif len(topic) == 3:
            self.score = topic[0] + 0.75 * topic[1] + 0.5 * topic[2]
    def __lt__(self, other):
        return (self.score < other.score)
    def toDict(self):
        temp = {}
        temp['key'] = self.index
        temp['name'] = self.name
        temp['qu'] = self.qu
        temp['topic'] = self.topic
        temp['posRate'] = self.posRate
        temp['time'] = self.time
        temp['lat'] = self.lat
        temp['lng'] = self.lng
        temp['score'] = self.score
        return temp

@app.route('/getSearch', methods=['POST'])
def search():
    #get parameters from frontend
    print(request.form)
    means = request.form.get('means')
    if means == "any":
        means = ''
    else:
        means = ':' + means
    place = request.form.get('place')
    transfer = request.form.get('transfer')
    time = request.form.get('time')
    topics = literal_eval(request.form.get('topics'))
    print(means, place, transfer, time, topics)
    #get all the candidates
    cypher = 'match (p1:Place{name:"%s"})-[%s*..%s]-(p2:Place) return distinct p2' % (place, means, transfer)
    result = graph.run(cypher).data()
    #print(result[0]['p2'])
    nodes = []
    minTimes = []
    for node in result:
        place2 = node['p2']['name']
        if means == 'bus' or means == 'subway':
            cypher2 = '''match (start:Place{name:"%s"}),(end:Place{name:"%s"})
                        call algo.shortestPath.stream(start,end,"time",{relationshipQuery:"%s",direction:"both"}) 
                        yield nodeId, cost 
                        return algo.getNodeById(nodeId).name as name, cost''' % (place, place2, means)
            result_time = graph.run(cypher2).data()
        else:
            cypher2 = '''match (start:Place{name:"%s"}),(end:Place{name:"%s"})
                        call algo.shortestPath.stream(start,end,"time",{relationshipQuery:null,direction:"both"}) 
                        yield nodeId, cost 
                        return algo.getNodeById(nodeId).name as name, cost''' % (place, place2)
            result_time = graph.run(cypher2).data()
        minTime = result_time[len(result_time) - 1]['cost']
        if minTime <= int(time):
            nodes.append(node)
            minTimes.append(minTime)
    places = []
    selectedTopics = []
    for t in topics:
        selectedTopics.append(topic_num[t])
    for i in range(0, len(nodes)):
        index = i
        name = nodes[i]['p2']['name']
        qu = nodes[i]['p2']['qu']
        topic = []
        posRate = []
        for t in selectedTopics:
            topic.append(nodes[i]['p2']['topic'+t])
            posRate.append(nodes[i]['p2']['posRate'+t])
        minTime = minTimes[i]
        lat = nodes[i]['p2']['lat']
        lng = nodes[i]['p2']['lng']
        temp = Place(index, name, qu, topic, posRate, minTime, lat, lng)
        places.append(temp)
    places.sort(reverse=True)
    places_response = []
    for i in range(0, len(places)):
        temp = places[i].toDict()
        temp['rank'] = i + 1
        places_response.append(temp)
    return Response(json.dumps({"places": places_response}), mimetype="application/json")

@app.route('/coordinate', methods=['POST'])
def coordinate():
    place = request.form.get('place')
    cypher = 'match (p:Place{name:"%s"}) return p.lat, p.lng' % place
    result = graph.run(cypher).data()
    coord = {'lat':result[0]['p.lat'], 'lng':result[0]['p.lng']}
    return Response(json.dumps(coord), mimetype="application/json")

@app.route('/viewbytopic', methods=['POST'])
def viewbytopic():
    topic = request.form.get('topic')
    #print(topic)
    cypher = 'match (p:Place) return p'
    nodes  = graph.run(cypher).data()
    places_response = []
    for i in range(0, len(nodes)):
        temp = {}
        temp['key'] = i
        temp['name'] = nodes[i]['p']['name']
        temp['qu'] = nodes[i]['p']['qu']
        temp['topic'] = round(10000 * nodes[i]['p']['topic'+topic_num[topic]], 2)
        temp['posRate'] = round(100 * nodes[i]['p']['posRate'+topic_num[topic]], 2)
        places_response.append(temp)
    return Response(json.dumps({"places": places_response}), mimetype="application/json")

@app.route('/neighbor', methods=['POST'])
def neighbor():
    place = request.form.get('place')
    means = request.form.get('means')
    if means == "any":
        means = ''
    else:
        means = ':' + means
    cypher = 'match (p1:Place{name:"%s"})-[r%s]-(p2:Place) return distinct p1, p2, r' % (place, means)
    result = graph.run(cypher).data()
    rel_response = {}
    rel_response["node"] = []
    rel_response["link"] = []
    nodeId = 0
    rel_response["node"].append({"name":place, "id":nodeId})
    nodeId += 1
    dest = []
    for record in result:
        if record['p2']['name'] not in dest:
            dest.append(record['p2']['name'])
            rel_response["node"].append({"name":record['p2']['name'], "id":nodeId})
            type_str = str(type(record['r']))
            rel_type = type_str[20:len(type_str)-2]
            #rel_response["link"].append({"source":0, "target":nodeId, "means":rel_type, "count":record['r']['count']})
            rel_response["link"].append({"source":0, "target":nodeId, "count":record['r']['count']})
            print(rel_response)
            nodeId += 1
        else:
            for node in rel_response["node"]:
                if node['name'] == record['p2']['name']:
                    tempId = node['id']
            for edge in rel_response["link"]:
                if edge["target"] == tempId:
                    edge["count"] += record['r']['count']
    return Response(json.dumps(rel_response), mimetype="application/json")



@app.route('/example', methods=['POST'])
def example():
    nodes = []
    nodes.append({"place": "五道口", "cityRegion": "海淀区"})
    nodes.append({"place": "中关村", "cityRegion": "海淀区"})

if __name__ == '__main__':
    app.run(debug=True)