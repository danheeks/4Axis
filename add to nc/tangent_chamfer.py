import tangent_knife
import nc

################################################################################
class Creator(tangent_knife.Creator):

    def __init__(self):
        tangent_knife.Creator.__init__(self)
        self.chamfer = 45.0
           
################################################################################

nc.creator = Creator()
