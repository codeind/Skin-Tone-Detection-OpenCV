# Importing required libraries
import numpy as np
import cv2
from sklearn.cluster import KMeans
from collections import Counter
import matplotlib.image as mpimg

from matplotlib import pyplot as plt

# Defining necessary functions


def extract_skin(image):
    img = image.copy()
    black_img = np.zeros((img.shape[0], img.shape[1], img.shape[2]), dtype=np.uint8)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    lower_threshold = np.array([0, 48, 80], dtype=np.uint8)
    print(lower_threshold)
    upper_threshold = np.array([20, 255, 255], dtype=np.uint8)
    print(upper_threshold)

    skin_mask = cv2.inRange(img, lower_threshold, upper_threshold)
    skin = cv2.bitwise_and(img, img, mask=skin_mask)
    return cv2.cvtColor(skin, cv2.COLOR_HSV2BGR)


def remove_black(estimator_labels, estimator_cluster):
    has_black = False
    occurance_counter = Counter(estimator_labels)
    def compare(x, y): return Counter(x) == Counter(y)
    for x in occurance_counter.most_common(len(estimator_cluster)):
        color = [int(i) for i in estimator_cluster[x[0]].tolist()]
        if compare(color, [0, 0, 0]):
            del occurance_counter[x[0]]
            has_black = True
            estimator_cluster = np.delete(estimator_cluster, x[0], 0)
            break

    return (occurance_counter, estimator_cluster, has_black)


def getColorInformation(estimator_labels, estimator_cluster, hasThresholding=False):
    occurance_counter = None
    colorInformation = []
    hasBlack = False
    if hasThresholding == True:
        (occurance, cluster, black) = remove_black(
            estimator_labels, estimator_cluster)
        occurance_counter = occurance
        estimator_cluster = cluster
        hasBlack = black
    else:
        occurance_counter = Counter(estimator_labels)
    totalOccurance = sum(occurance_counter.values())
    for x in occurance_counter.most_common(len(estimator_cluster)):
        index = (int(x[0]))
        index = (index-1) if ((hasThresholding & hasBlack)
                              & (int(index) != 0)) else index
        color = estimator_cluster[index].tolist()
        color_percentage = (x[1]/totalOccurance)
        colorInfo = {"cluster_index": index, "color": color,
                     "color_percentage": color_percentage}
        colorInformation.append(colorInfo)
    return colorInformation


def extractDominantColor(image, number_of_colors=1, hasThresholding=False):
    if hasThresholding == True:
        number_of_colors += 1
    img = image.copy()
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img = img.reshape((img.shape[0]*img.shape[1]), 3)
    estimator = KMeans(n_clusters=number_of_colors, random_state=0)
    estimator.fit(img)
    colorInformation = getColorInformation(
        estimator.labels_, estimator.cluster_centers_, hasThresholding)
    return colorInformation


def plotColorBar(colorInformation):
    color_bar = np.zeros((100, 500, 3), dtype="uint8")
    top_x = 0
    for x in colorInformation:
        bottom_x = top_x + (x["color_percentage"] * color_bar.shape[1])
        color = tuple(map(int, (x['color'])))
        cv2.rectangle(color_bar, (int(top_x), 0),
                      (int(bottom_x), color_bar.shape[0]), color, -1)
        top_x = bottom_x
    return color_bar


# Main Program Execution
def run():
    rgb_lower = [85, 52, 56]
    rgb_higher = [255, 219, 172]
    skin_shades = {
        'dark': [[0, 0, 0], [141, 89, 85]],
        'mild': [[141, 89, 85], [159, 118, 85]],
        'fair': [[159, 118, 85], [255, 255, 255]]
    }

    convert_skintones = {}
    for shade in skin_shades:
        convert_skintones.update({
            shade: [
                (skin_shades[shade][0][0] * 256 * 256) + (skin_shades[shade][0][1] * 256) + skin_shades[shade][0][2],
                (skin_shades[shade][1][0] * 256 * 256) + (skin_shades[shade][1][1] * 256) + skin_shades[shade][1][2]
            ]
        })

    image = mpimg.imread('uploaded-image.jpg')
    skin = extract_skin(image)

    unprocessed_dominant = extractDominantColor(skin, number_of_colors=1, hasThresholding=True)

    decimal_lower = (rgb_lower[0] * 256 * 256) + (rgb_lower[1] * 255) + rgb_lower[2]
    decimal_higher = (rgb_higher[0] * 265 * 256) + (rgb_higher[1] * 255) + rgb_higher[2]

    dominant_colors = []
    for clr in unprocessed_dominant:
        clr_decimal = int((clr['color'][0] * 256 * 256) + (clr['color'][1] * 256) + clr['color'][2])
        if clr_decimal in range(decimal_lower, decimal_higher+1):
            clr['decimal_color'] = clr_decimal
            dominant_colors.append(clr)

    # Data Result variable
    skin_tones = []
    if len(dominant_colors) == 0:
        skin_tones.append('Unrecognized')
    else:
        for color in dominant_colors:
            for shade in convert_skintones:
                if color['decimal_color'] in range(convert_skintones[shade][0], convert_skintones[shade][1]+1):
                    skin_tones.append(shade)

    result = {
        'result': skin_tones[0],
        'colorR': dominant_colors[0]['color'][0],
        'colorG': dominant_colors[0]['color'][1],
        'colorB': dominant_colors[0]['color'][2],
    }
    return result
