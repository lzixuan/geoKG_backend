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
        temp['index'] = self.index
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
    place = request.form.get('place')
    transfer = request.form.get('transfer')
    time = request.form.get('time')
    topics = literal_eval(request.form.get('topics'))
    print(means, place, transfer, time, topics)
    #get all the candidates
    cypher = 'match (p1:Place{name:"%s"})-[:%s*..%s]-(p2:Place) return distinct p2' % (place, means, transfer)
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
            minTime = result_time[len(result_time) - 1]['cost']
        else:
            cypher2 = '''match (start:Place{name:"%s"}),(end:Place{name:"%s"})
                        call algo.shortestPath.stream(start,end,"time",{relationshipQuery:"bus",direction:"both"}) 
                        yield nodeId, cost 
                        return algo.getNodeById(nodeId).name as name, cost''' % (place, place2)
            result_time = graph.run(cypher2).data()
            minTime1 = result_time[len(result_time) - 1]['cost']
            cypher2 = '''match (start:Place{name:"%s"}),(end:Place{name:"%s"})
                        call algo.shortestPath.stream(start,end,"time",{relationshipQuery:"subway",direction:"both"}) 
                        yield nodeId, cost 
                        return algo.getNodeById(nodeId).name as name, cost''' % (place, place2)
            result_time = graph.run(cypher2).data()
            minTime2 = result_time[len(result_time) - 1]['cost']
            minTime = min(minTime1, minTime2)
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

@app.route('/example', methods=['POST'])
def example():
    nodes = []
    nodes.append({"place": "五道口", "cityRegion": "海淀区"})
    nodes.append({"place": "中关村", "cityRegion": "海淀区"})

if __name__ == '__main__':
    app.run(debug=True)