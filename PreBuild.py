# increment build number

f = open('Build Defines Auto Generated.txt', 'r')
line1 = f.readline()
line2 = f.readline()

s = line2.split(' ')
v = s[2][3:-2]

v = int(v) + 1

f.close()


f = open('Build Defines Auto Generated.txt', 'w')

f.write('#define MyAppName "Four Axis Heeks"\n')
f.write('#define MyVersion "0.' + str(v) + '"\n')

f.close()