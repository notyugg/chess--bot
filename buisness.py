tiles = [
    {"name":"Go", "type":"Special"},
    {"name":"Mumbai", "type": "property","price":6000},
    {"name":"Chance", "type":"Special"},
    {"name":"Delhi","type":"property","price":8000}  
]
print(tiles[1]["name"])

class Player:
    def __init__(self,name):
        self.name = name
        self.money = 15000
        self.position = 0

players = [Player("Yug"),Player("Rahul")]
print(tiles[players[0].position]["name"])

