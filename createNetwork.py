from comm_module import createBroadcastServer
import datetime
from math import floor, sqrt, log
import json
from random import choice, randint
import os    
from time import time
from simulaqron.network import Network
import subprocess
import sys, getopt

from comm_module import getConfigPort
import os

DEBUG = "test_simulation" # "simulation" # 


# Generates a JSON file with default params in order to run simulation
# @param nodes: number of nodes to simulate
# @param fidelity: fidelity of the GHZ state generated by the source. It is used in order to
#                  get also the epsilon value
# @param delta: probability that the protocol doesn't abort.
# @param S: security parameter.
# @param ordering: order of the nodes 
def generateJSONFile(nodes, fidelity, delta, verb):
    with open('conf.json', 'w') as f:
        data = {}
        params = {}
        params['n_nodes'] = nodes
        params['fidelity'] = fidelity
        params['delta'] = delta
        params['epsilon'] = sqrt(1 - fidelity**2) 
        if fidelity != 1:
            params['S'] = round(log( (4*nodes)/((1-sqrt(1-params['epsilon']**2))*delta), 2))
        else:
            params['S'] = 10
        params['verbose'] = verb
        data['params'] = params

        data['ordering'] = [i for i in range(nodes)]        
        json.dump(data, f)
    return data

if __name__ == '__main__':
    delta = 0.01
    fidelity = 1
    generate = False
    honest_verifier = False
    unentangled_adv = True
    n_adversaries = 0
    nodes_to_create = 3
    verbose = 2

    opts, args = getopt.getopt(sys.argv[1:], 'n:f:d:a:h:v',['nodes=','fidelity=','delta=','adv=','help=','honest-verifier=','verbose=','unentangled-adv='])
    for opt, arg in opts:
        if opt in ('-n', '--nodes'):
            nodes_to_create = int(arg)
        elif opt in ('-f', '--fidelity'):
            fidelity = float(arg)
        elif opt in ('-d', '--delta'):
            delta = float(arg)
        elif opt in ('-v', '--verbose'):
            verbose = int(arg)
        elif opt in ('-a', '--adv'):
            n_adversaries = int(arg)
        elif opt in ('--honest-verifier'): #the verifier is always honest
            assert arg in ['0','1'], "wrong honest verifier parameter"
            honest_verifier = bool(int(arg))
        elif opt in ('--unentangled-adv'): #the adversaries qubits are unentangled in the GHZ state generation
            assert arg in ['0','1'], "wrong unentangled adversaries qubits parameter"
            unentangled_adv = bool(int(arg))
        elif opt in ('-h', '--help'):
            print('Supported commands:'+
                    '\n {:3s}  {:12s} -> sets the number of adversaries'.format('-a','--adv')+
                    '\n {:3s}  {:12s} -> sets the delta parameter'.format('-d','--delta')+
                    '\n {:3s}  {:12s} -> enable a dishonest verifier to be chosen (input 0 or 1)'.format('','--honest-verifier')+
                    '\n {:3s}  {:12s} -> changes fidelity parameter'.format('-f','--fidelity')+
                    '\n {:3s}  {:12s} -> print commands'.format('-h','--help')+
                    '\n {:3s}  {:12s} -> sets nodes number'.format('-n','--nodes')+
                    '\n {:3s}  {:12s} -> toggle verbose mode (1 enabled, 0 disabled)'.format('-v','--verbose'))
            exit()
        else:
            assert False, "unknwown option"
    
    
    if not os.path.exists('conf.json'):
        print('Missing conf.json file. Generating a new one')
        generate = True
    else:
        with open('conf.json', 'r') as f:
            try:
                conf = json.load(f)
                if (conf['params']['n_nodes'] != nodes_to_create or 
                        conf['params']['delta'] != delta or
                        conf['params']['fidelity'] != fidelity or
                        conf['params']['verbose'] != verbose):
                    generate = True
            except:
                print('Wrong conf.json format or missing arguments, generating a new one')
                generate = True

    if generate:    
        generateJSONFile(nodes_to_create, fidelity, delta, verbose)
        print('conf.json file created!\n')

    with open('conf.json', 'r') as f:
        conf = json.load(f)

    n_nodes = int(conf['params']['n_nodes'])
    
    node_list = ['node'+str(i) for i in range(0, n_nodes)]
    network = Network(nodes=node_list, topology='complete')
    network.start()


    # the sender won't be the source of ghz states
    sender = randint(0, n_nodes-2)
    adversary = []
    if n_adversaries > 0:
        possible_adversary = [i for i in range(0, n_nodes)]
        possible_adversary.pop(sender)

        # the adversaries have always the control of the ghz source
        n_adversaries -= 1
        adversary.append(possible_adversary[-1])
        possible_adversary.pop(possible_adversary.index(adversary[-1]))

        for _ in range(n_adversaries):
            selected = choice(possible_adversary)
            adversary.append(selected)
            possible_adversary.pop(possible_adversary.index(selected))


    # This json avoids that the verifier is an adversary. 
    # It is useful when we want to simulate a specific situations
    if honest_verifier:
        print('adv.json file generated')
        with open('adv.json',"w") as adv_json:
            adv = {}
            adv['adversary'] = adversary
            json.dump(adv, adv_json)
    else:
        if os.path.exists('adv.json'):
            os.remove('adv.json')

    fidelity = conf['params']['fidelity']
    delta = conf['params']['delta']
    epsilon = conf['params']['epsilon']
    S = conf['params']['S']
    order = conf['ordering']


    # Pretty-print simulation parameters on file
    timestamp = str(datetime.datetime.fromtimestamp(time()).strftime('%Y-%m-%d %H:%M:%S'))
    simulation_parameters = ('simulation parameters:'+
            '\n\ttimestamp: '+timestamp+
            '\n\tnodes: '+str(n_nodes)+
            '\n\tsender: '+str(sender)+
            '\n\tadversaries: '+ str(adversary)+
            '\n\tdelta: {0:.2f}'.format(delta)+
            '\n\tGHZ states fidelity and epsilon: {0:.2f} {1:.2f}'.format(fidelity, epsilon)+
            '\n\tsecurity parameter (S): {}'.format(S)+
            '\n\tordering: '+str(order))

    if honest_verifier:
        simulation_parameters += ('\n\thonest verifier: '+str(honest_verifier))    
    if len(adversary) > 0:
        simulation_parameters += ('\n\tunentangled qubits for adversaries: '+str(unentangled_adv))
    simulation_parameters += '\n'
    print(simulation_parameters)

    with open("./results/"+DEBUG+"_"+str(n_nodes)+".csv","a") as output:
        print(simulation_parameters,file=output)

    # spawns processes for each agent
    for i in range(0, n_nodes):
        params = "python3 node.py "+str(i)+" "

        if (i == sender):
            params += "1 "
        else:
            if len(adversary) > 0 and i in adversary:
                to_append = "2 " + str("-".join(map(str, adversary))) + " " + str(int(unentangled_adv)) +" "
                params += to_append
            else:
                params += "0 "    

        if i != n_nodes -1:
            params += "&"
        subprocess.call(params, shell = True)

    # runs the broadcast server in background and creates a new communication
    # layer (classical) for each node
    createBroadcastServer()