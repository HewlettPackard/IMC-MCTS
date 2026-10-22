# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Functional policy oracle: Python lists, no mapped SRAM or simulator control.
from core.architecture.ucb_arithmetic import next_choice, score


class Reference:
    def __init__(self, board, evaluate, seed=0, exploration=1.414, game=None, state=None):
        self.game=game; self.evaluate=evaluate; self.exploration=exploration
        self.random_state=seed or 0x6d2b79f5
        player=1 if game is None else state['current_player']
        self.nodes=[{'board':board.copy(),'player':player,'parent':-1,'children':[],
            'visits':0,'value':0.0,'untried':None,'state':state,'move':None}]
        self.history=[]

    def step(self):
        current=0; path=[]
        while True:
            node=self.nodes[current]; path.append(current)
            if not node['visits']: break
            if node['untried'] is None:
                if self.game is None:
                    node['untried']=[i for i,v in enumerate(node['board'].flat) if v==0]
                else:
                    node['untried']=[] if self.game.is_terminal(node['state']) else list(self.game.get_legal_moves(node['state']))
            if node['untried'] or not node['children']: break
            current=max(node['children'],key=lambda child:score(node['visits'],self.nodes[child]['visits'],
                self.nodes[child]['value'],self.exploration))
        if node['visits'] and node['untried']:
            self.random_state=next_choice(self.random_state)
            move=node['untried'].pop(self.random_state%len(node['untried']))
            if self.game is None:
                board=node['board'].copy(); board.flat[move]=node['player']; state=None
            else:
                state=self.game.apply_move(node['state'],move); board=state['board'].copy()
            child=len(self.nodes); node['children'].append(child)
            self.nodes.append({'board':board,'player':-node['player'],'parent':current,
                'children':[],'visits':0,'value':0.0,'untried':None,'state':state,'move':move})
            current=child; path.append(current); node=self.nodes[current]
        value=self.evaluate(node['board'],node['player'])
        if self.game is not None and self.game.is_terminal(node['state']):
            value=round(self.game.get_result_black(node['state'])*131072)
        for index in path:
            visited=self.nodes[index]; visited['visits']+=1
            visited['value']+=(value if visited['player']==1 else 131072-value)/131072
        result={'selected':current,'value_q17':value,'nodes':len(self.nodes),'random_state':self.random_state}
        self.history.append(result)
        return result
