import urequests

while(True):
    print("Sun intensity")

    url_sun = "https://icelec50015.azurewebsites.net/sun"

    response1 = urequests.get(url_sun)

    if response1.status_code == 200:
        data1 = response1.json()
        for key in data1:
            print(f"{key}: {data1[key]}")
    else:
        print("Error:", response1.status_code)

    response1.close()

    print("energy prices")

    url_price = "https://icelec50015.azurewebsites.net/price"

    response2 = urequests.get(url_price)

    if response2.status_code == 200:
        data2 = response2.json()
        for key in data2:
            print(f"{key}: {data2[key]}")
    else:
        print("Error:", response2.status_code)

    response2.close()

    print("power demand")

    url_demand = "https://icelec50015.azurewebsites.net/demand"

    response3 = urequests.get(url_demand)

    if response3.status_code == 200:
        data3 = response3.json()
        for key in data3:
            print(f"{key}: {data3[key]}")
    else:
        print("Error:", response3.status_code)

    response3.close()

    print("deferable demands")

    url_deferables = "https://icelec50015.azurewebsites.net/deferables"

    response4 = urequests.get(url_deferables)

    if response4.status_code == 200:
        data4 = response4.json()
        for dict in data4:
            for key in dict:
                print(f"{key}: {dict[key]}")
    else:
        print("Error:", response4.status_code)

    response4.close()

    print("yesterday price and demand")

    url_yesterday = "https://icelec50015.azurewebsites.net/yesterday"

    response5 = urequests.get(url_price)

    if response5.status_code == 200:
        data5 = response5.json()
        for key in data5:
            print(f"{key}: {data5[key]}")
    else:
        print("Error:", response5.status_code)

    response5.close()
