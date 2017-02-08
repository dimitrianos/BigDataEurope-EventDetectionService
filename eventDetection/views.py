import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.utils.datastructures import MultiValueDictKeyError

def index(request):
    return HttpResponse("Please use the API call \"search\"<br>e.g., http://localhost:8000/eventDetection/search?extent=POINT(1%2010)&reference_date=2016-01-01&event_date=2017-01-01&keys=Camp")
def search(request):
    # Get the parameters from user
    try:
        extent=request.GET.get('extent',None)
        keys=request.GET.get('keys',None)
        event_date=request.GET.get('event_date',None)
        reference_date=request.GET.get('reference_date',None)
    except MultiValueDictKeyError as e:
        return HttpResponseBadRequest('Missing parameters. Please provide all: <ol><li>extent</li><li>event_date</li><li>reference_date</li><li>keys</li></ol>')

    # try parsing dates according to ISO8601
    try:
        if event_date and event_date!='null':
            event_date=datetime.strptime(event_date,"%Y-%m-%d")
        if reference_date and reference_date!='null':
            reference_date=datetime.strptime(reference_date,"%Y-%m-%d")
    except ValueError as e:
        return HttpResponseBadRequest('date should be <b>ISO8601</b> format')
    
    if keys:
        keys = keys.replace(",", "|");

    q=query(extent,keys,event_date,reference_date)
    print(q)
    
    headers = {'content-type': 'application/x-www-form-urlencoded', 'Accept' : 'application/sparql-results+xml'}
    url = "http://semagrow_bde:8080/SemaGrow/sparql"
    #url="http://test.strabon.di.uoa.gr/MELODIES/Query";
    params = {"query" : q, 'format':'SPARQL/XML'}
    r=requests.post(url, params=params, headers=headers)

    print(r.status_code, r.reason)
    print(r.text)
    # parse xml data to build the objects
    tree = ET.ElementTree(ET.fromstring(r.text))
    results=tree.find('{http://www.w3.org/2005/sparql-results#}results')
    events={}
    for result in results:
        bindings=result.findall('{http://www.w3.org/2005/sparql-results#}binding')
        #print(bindings)
        #bindings[0][0].text # ignore this one
        event_id=''
        title=''
        date=''
        gwkt=''
        name=''
        for binding in bindings:
            if binding.attrib['name'] == 'id':
                event_id=binding[0].text
            elif binding.attrib['name'] == 't':
                title=binding[0].text
            elif binding.attrib['name'] == 'd':
                date=binding[0].text
            elif binding.attrib['name'] == 'w':
                gwkt=binding[0].text
            elif binding.attrib['name'] == 'n':
                name=binding[0].text

        # event_id=bindings[1][0].text
        # title=bindings[2][0].text
        # date=bindings[3][0].text
        # gwkt=bindings[4][0].text
        # name=bindings[5][0].text
        event={'id':event_id,'title':title,'eventDate':date,'areas':[{'name':name,'geometry':gwkt}]}
        
        #if event's id already in our dictionary then add the new geometry to its list of geometries
        if event_id in events:
            events[event_id]['areas'].append({'name':name,'geometry':gwkt})
        else:
            events[event_id]=event
    return HttpResponse(json.dumps(list(events.values())) , content_type="application/json")

# Build the query
def query(extent,keys,event_date,reference_date):
    select ="SELECT distinct ?e ?id ?t ?d ?w ?n";
    #filters = "filter(";
    prefixes = '\n'.join(('PREFIX geo: <http://www.opengis.net/ont/geosparql#>',
    'PREFIX strdf: <http://strdf.di.uoa.gr/ontology#>',
    'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>',
    'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>',
    'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>',
    'PREFIX ev: <http://big-data-europe.eu/security/man-made-changes/ontology#>'));
    where = '\n'.join(('WHERE{',' ?e rdf:type ev:NewsEvent . ', ' ?e ev:hasId ?id . ?e ev:hasTitle ?t . ',
    ' ?e ev:hasDate ?d . ','?e ev:hasArea ?a . ', '?a ev:hasName ?n . ',' ?a geo:hasGeometry ?g . ',  
    ' ?g geo:asWKT ?w .'));
    filters=[]
    if event_date and event_date != 'null':
        filters.append("?d < '" + str(event_date) + "'^^xsd:dateTime")
    if reference_date and reference_date != 'null':
        filters.append("?d > '" + str(reference_date) + "'^^xsd:dateTime")
    if keys and keys != 'null':
        filters.append("regex(?t, '" + str(keys) + "','i')")
    if extent and extent != 'null':
        filters.append("strdf:intersects(?w,'" + str(extent) + "')")
    if filters and extent != 'null':
        where += 'FILTER('+' && '.join(filters) + ")}"
    else:
        where += '}'

    q = '\n'.join((prefixes ,select , where ))
    #q = "SELECT distinct ?e ?id ?t ?d ?w ?n WHERE {BIND(<http://mpla> AS ?t)}"
    return q