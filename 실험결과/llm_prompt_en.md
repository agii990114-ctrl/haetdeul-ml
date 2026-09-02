# Wholesale auction price forecast - fill in 18 steps

You forecast agricultural wholesale prices. Using only the information below,
give the **auction price (KRW per kg) at Seoul Garak market for each of the
next 1 to 18 business days**.

## Rules

- **Use only the numbers given.** Do not bring in news or outside knowledge
- Dates are deliberately hidden. Do not try to guess when this is
- Give **18 numbers** per block (1 business day ahead ... 18 business days ahead)
- **Write no explanation.** Output only the lines in the format below

## Output format

```
BlockID|day1,day2,day3,...,day18
```

Example (the numbers are only an example):

```
B01|812,818,825,830,833,840,845,848,850,855,858,860,862,865,868,870,872,875
```

**Give 30 lines for all 30 blocks. Write nothing else.**

## Notes - what these values mean

- **Starting point**: yesterday's price blended with the last 7-day mean.
  The answer is often near this. But leaving it unchanged is the same as
  doing nothing
- **Auction price**: the price struck at auction. Lower than wholesale and
  retail prices
- **Main growing-area station**: the weather station of the main growing
  area for that period
- Prices are KRW per kg; arrivals are in tonnes

---


## B01 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **445.7 KRW/kg** |
| Auction price, 3 days ago | 631.5 |
| Auction price, last 7-day mean | 478.2 |
| Auction grade spread | 3.855 |
| Auction volume (kg) | 196,540 |
| Wholesale / auction ratio | 2.066 |
| Wholesale price, yesterday | 820 |
| Wholesale price, 3 days ago | 1,140 |
| Wholesale price, 7 days ago | 890 |
| Wholesale price, 7-day mean | 941.4 |
| Wholesale price, 14-day mean | 896.1 |
| Wholesale price, 7-day std dev | 139.2 |
| Arrivals yesterday (tonnes) | 325 |
| Arrivals, 7-day mean (tonnes) | 311.4 |
| Retail price, yesterday | 3,305.7 |
| Temperature at the market city | 24.3 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 115 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 1,045 | 354.3 |
| **2** | Thu | 113 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 1,086.7 | 368.2 |
| **3** | Fri | 112 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 1,086.7 | 368.2 |
| **4** | Mon | 109 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 985 | 361 |
| **5** | Tue | 108 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 945 | 340.3 |
| **6** | Wed | 107 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 956 | 326.5 |
| **7** | Thu | 106 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 956 | 318.3 |
| **8** | Fri | 105 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 956 | 318.3 |
| **9** | Mon | 102 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 950 | 411.5 |
| **10** | Tue | 101 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 946 | 431.5 |
| **11** | Wed | 100 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 954 | 437.8 |
| **12** | Thu | 99 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 954 | 439.8 |
| **13** | Fri | 98 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 954 | 439.8 |
| **14** | Mon | 95 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 908 | 438 |
| **15** | Tue | 94 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 904 | 416.3 |
| **16** | Wed | 93 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 864 | 444.8 |
| **17** | Thu | 92 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 864 | 459 |
| **18** | Fri | 91 | 0 | 대관령 | 19.4 | 1.900 | 125 | 287.5 | 16.2 | 864 | 459 |

## B02 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **655.0 KRW/kg** |
| Auction price, 3 days ago | 613.9 |
| Auction price, last 7-day mean | 646.9 |
| Auction grade spread | 1.454 |
| Auction volume (kg) | 391,720 |
| Wholesale / auction ratio | 1.330 |
| Wholesale price, yesterday | 887.5 |
| Wholesale price, 3 days ago | 852.5 |
| Wholesale price, 7 days ago | 915 |
| Wholesale price, 7-day mean | 849.3 |
| Wholesale price, 14-day mean | 877.1 |
| Wholesale price, 7-day std dev | 52.1 |
| Arrivals yesterday (tonnes) | 341 |
| Arrivals, 7-day mean (tonnes) | 455.6 |
| Retail price, yesterday | 1,957.5 |
| Temperature at the market city | 24.3 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 115 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 981.2 | 526.7 |
| **2** | Thu | 113 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 970.8 | 518.2 |
| **3** | Fri | 112 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 970.8 | 518.2 |
| **4** | Mon | 109 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 916.2 | 531.2 |
| **5** | Tue | 108 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 926.9 | 518.5 |
| **6** | Wed | 107 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 935 | 490.3 |
| **7** | Thu | 106 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 935 | 481.5 |
| **8** | Fri | 105 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 935 | 481.5 |
| **9** | Mon | 102 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 880 | 506.7 |
| **10** | Tue | 101 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 854 | 505.3 |
| **11** | Wed | 100 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 815.5 | 489 |
| **12** | Thu | 99 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 815.5 | 492.7 |
| **13** | Fri | 98 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 815.5 | 492.7 |
| **14** | Mon | 95 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 706.5 | 462.2 |
| **15** | Tue | 94 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 709 | 423.8 |
| **16** | Wed | 93 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 694 | 455.5 |
| **17** | Thu | 92 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 694 | 463.3 |
| **18** | Fri | 91 | 0 | 고창군 | 21.7 | 15.6 | 101.4 | 402.4 | 21.2 | 694 | 463.3 |

## B03 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **629.1 KRW/kg** |
| Auction price, 3 days ago | 551.6 |
| Auction price, last 7-day mean | 593.6 |
| Auction grade spread | 0.831 |
| Auction volume (kg) | 603,615 |
| Wholesale / auction ratio | 1.055 |
| Wholesale price, yesterday | 720 |
| Wholesale price, 3 days ago | 706.7 |
| Wholesale price, 7 days ago | 706.7 |
| Wholesale price, 7-day mean | 710.5 |
| Wholesale price, 14-day mean | 717.1 |
| Wholesale price, 7-day std dev | 6.506 |
| Arrivals yesterday (tonnes) | 994 |
| Arrivals, 7-day mean (tonnes) | 1,023.1 |
| Retail price, yesterday | 1,771.3 |
| Temperature at the market city | 24.3 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 115 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 686.7 | 1,043 |
| **2** | Thu | 113 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 686.7 | 1,047.7 |
| **3** | Fri | 112 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 686.7 | 1,047.7 |
| **4** | Mon | 109 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 700 | 965 |
| **5** | Tue | 108 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 711.7 | 926.8 |
| **6** | Wed | 107 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 716 | 866.3 |
| **7** | Thu | 106 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 716 | 859.7 |
| **8** | Fri | 105 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 716 | 859.7 |
| **9** | Mon | 102 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 768 | 752.5 |
| **10** | Tue | 101 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 818.7 | 692 |
| **11** | Wed | 100 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 869.3 | 705.2 |
| **12** | Thu | 99 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 869.3 | 714.3 |
| **13** | Fri | 98 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 869.3 | 714.3 |
| **14** | Mon | 95 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 1,025.3 | 715.8 |
| **15** | Tue | 94 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 1,032 | 737.8 |
| **16** | Wed | 93 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 992 | 742.2 |
| **17** | Thu | 92 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 992 | 720 |
| **18** | Fri | 91 | 0 | 목포 | 22.6 | 9.600 | 115.4 | 409.2 | 21.2 | 992 | 720 |

## B04 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **449.6 KRW/kg** |
| Auction price, 3 days ago | 553.0 |
| Auction price, last 7-day mean | 504.4 |
| Auction grade spread | 2.449 |
| Auction volume (kg) | 318,520 |
| Wholesale / auction ratio | 2.449 |
| Wholesale price, yesterday | 900 |
| Wholesale price, 3 days ago | 900 |
| Wholesale price, 7 days ago | 820 |
| Wholesale price, 7-day mean | 854.3 |
| Wholesale price, 14-day mean | 901.8 |
| Wholesale price, 7-day std dev | 42.8 |
| Arrivals yesterday (tonnes) | 399 |
| Arrivals, 7-day mean (tonnes) | 376.2 |
| Retail price, yesterday | 3,501.2 |
| Temperature at the market city | 21.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Wed | 107 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 956 | 326.5 |
| **2** | Thu | 106 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 956 | 318.3 |
| **3** | Fri | 105 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 956 | 318.3 |
| **4** | Mon | 102 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 950 | 411.5 |
| **5** | Tue | 101 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 946 | 431.5 |
| **6** | Wed | 100 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 954 | 437.8 |
| **7** | Thu | 99 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 954 | 439.8 |
| **8** | Fri | 98 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 954 | 439.8 |
| **9** | Mon | 95 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 908 | 438 |
| **10** | Tue | 94 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 904 | 416.3 |
| **11** | Wed | 93 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 864 | 444.8 |
| **12** | Thu | 92 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 864 | 459 |
| **13** | Fri | 91 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 864 | 459 |
| **14** | Mon | 88 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 936 | 407.2 |
| **15** | Tue | 87 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 932 | 452.5 |
| **16** | Wed | 86 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 952 | 430.2 |
| **17** | Thu | 85 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 952 | 403.5 |
| **18** | Fri | 84 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 952 | 403.5 |

## B05 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **565.0 KRW/kg** |
| Auction price, 3 days ago | 653.7 |
| Auction price, last 7-day mean | 583.8 |
| Auction grade spread | 1.770 |
| Auction volume (kg) | 491,700 |
| Wholesale / auction ratio | 1.611 |
| Wholesale price, yesterday | 865 |
| Wholesale price, 3 days ago | 865 |
| Wholesale price, 7 days ago | 887.5 |
| Wholesale price, 7-day mean | 875.7 |
| Wholesale price, 14-day mean | 861.4 |
| Wholesale price, 7-day std dev | 11.3 |
| Arrivals yesterday (tonnes) | 564 |
| Arrivals, 7-day mean (tonnes) | 471.1 |
| Retail price, yesterday | 1,968.6 |
| Temperature at the market city | 21.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Wed | 107 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 935 | 490.3 |
| **2** | Thu | 106 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 935 | 481.5 |
| **3** | Fri | 105 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 935 | 481.5 |
| **4** | Mon | 102 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 880 | 506.7 |
| **5** | Tue | 101 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 854 | 505.3 |
| **6** | Wed | 100 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 815.5 | 489 |
| **7** | Thu | 99 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 815.5 | 492.7 |
| **8** | Fri | 98 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 815.5 | 492.7 |
| **9** | Mon | 95 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 706.5 | 462.2 |
| **10** | Tue | 94 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 709 | 423.8 |
| **11** | Wed | 93 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 694 | 455.5 |
| **12** | Thu | 92 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 694 | 463.3 |
| **13** | Fri | 91 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 694 | 463.3 |
| **14** | Mon | 88 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 669 | 449.5 |
| **15** | Tue | 87 | 0 | 고창군 | 18.9 | 0 | 83.4 | 395.1 | 22.2 | 606 | 473.8 |
| **16** | Wed | 86 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 581 | 446.8 |
| **17** | Thu | 85 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 581 | 446.7 |
| **18** | Fri | 84 | 0 | 대관령 | 13.1 | 18.9 | 115.5 | 329.3 | 17.1 | 581 | 446.7 |

## B06 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **629.8 KRW/kg** |
| Auction price, 3 days ago | 655.5 |
| Auction price, last 7-day mean | 649.8 |
| Auction grade spread | 1.034 |
| Auction volume (kg) | 655,860 |
| Wholesale / auction ratio | 1.223 |
| Wholesale price, yesterday | 733.3 |
| Wholesale price, 3 days ago | 733.3 |
| Wholesale price, 7 days ago | 720 |
| Wholesale price, 7-day mean | 727.6 |
| Wholesale price, 14-day mean | 716.2 |
| Wholesale price, 7-day std dev | 7.127 |
| Arrivals yesterday (tonnes) | 876 |
| Arrivals, 7-day mean (tonnes) | 1,104.3 |
| Retail price, yesterday | 1,853.3 |
| Temperature at the market city | 21.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Wed | 107 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 716 | 866.3 |
| **2** | Thu | 106 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 716 | 859.7 |
| **3** | Fri | 105 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 716 | 859.7 |
| **4** | Mon | 102 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 768 | 752.5 |
| **5** | Tue | 101 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 818.7 | 692 |
| **6** | Wed | 100 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 869.3 | 705.2 |
| **7** | Thu | 99 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 869.3 | 714.3 |
| **8** | Fri | 98 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 869.3 | 714.3 |
| **9** | Mon | 95 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 1,025.3 | 715.8 |
| **10** | Tue | 94 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 1,032 | 737.8 |
| **11** | Wed | 93 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 992 | 742.2 |
| **12** | Thu | 92 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 992 | 720 |
| **13** | Fri | 91 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 992 | 720 |
| **14** | Mon | 88 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 832 | 677.3 |
| **15** | Tue | 87 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 814.7 | 663.8 |
| **16** | Wed | 86 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 844 | 633.7 |
| **17** | Thu | 85 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 844 | 644.2 |
| **18** | Fri | 84 | 0 | 목포 | 19.5 | 23.8 | 129.5 | 463.5 | 22.2 | 844 | 644.2 |

## B07 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **451.3 KRW/kg** |
| Auction price, 3 days ago | 466.5 |
| Auction price, last 7-day mean | 455.8 |
| Auction grade spread | 2.316 |
| Auction volume (kg) | 261,770 |
| Wholesale / auction ratio | 1.934 |
| Wholesale price, yesterday | 860 |
| Wholesale price, 3 days ago | 840 |
| Wholesale price, 7 days ago | 900 |
| Wholesale price, 7-day mean | 865.7 |
| Wholesale price, 14-day mean | 877.1 |
| Wholesale price, 7-day std dev | 25.1 |
| Arrivals yesterday (tonnes) | 282 |
| Arrivals, 7-day mean (tonnes) | 304.1 |
| Retail price, yesterday | 3,655 |
| Temperature at the market city | 27 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 99 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 954 | 439.8 |
| **2** | Fri | 98 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 954 | 439.8 |
| **3** | Mon | 95 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 908 | 438 |
| **4** | Tue | 94 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 904 | 416.3 |
| **5** | Wed | 93 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 864 | 444.8 |
| **6** | Thu | 92 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 864 | 459 |
| **7** | Fri | 91 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 864 | 459 |
| **8** | Mon | 88 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 936 | 407.2 |
| **9** | Tue | 87 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 932 | 452.5 |
| **10** | Wed | 86 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 952 | 430.2 |
| **11** | Thu | 85 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 952 | 403.5 |
| **12** | Fri | 84 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 952 | 403.5 |
| **13** | Mon | 81 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 1,072 | 410.5 |
| **14** | Tue | 80 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 1,116 | 374.8 |
| **16** | Thu | 78 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 1,208 | 381 |
| **17** | Fri | 77 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 1,208 | 381 |
| **18** | Mon | 74 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 1,392 | 393.8 |

## B08 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **626.5 KRW/kg** |
| Auction price, 3 days ago | 732.8 |
| Auction price, last 7-day mean | 638.9 |
| Auction grade spread | 1.538 |
| Auction volume (kg) | 405,560 |
| Wholesale / auction ratio | 1.641 |
| Wholesale price, yesterday | 997.5 |
| Wholesale price, 3 days ago | 997.5 |
| Wholesale price, 7 days ago | 865 |
| Wholesale price, 7-day mean | 965.4 |
| Wholesale price, 14-day mean | 919.6 |
| Wholesale price, 7-day std dev | 49.4 |
| Arrivals yesterday (tonnes) | 484 |
| Arrivals, 7-day mean (tonnes) | 457.6 |
| Retail price, yesterday | 1,711.4 |
| Temperature at the market city | 27 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 99 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 815.5 | 492.7 |
| **2** | Fri | 98 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 815.5 | 492.7 |
| **3** | Mon | 95 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 706.5 | 462.2 |
| **4** | Tue | 94 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 709 | 423.8 |
| **5** | Wed | 93 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 694 | 455.5 |
| **6** | Thu | 92 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 694 | 463.3 |
| **7** | Fri | 91 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 694 | 463.3 |
| **8** | Mon | 88 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 669 | 449.5 |
| **9** | Tue | 87 | 0 | 고창군 | 24.7 | 35.1 | 90 | 403.2 | 23.1 | 606 | 473.8 |
| **10** | Wed | 86 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 581 | 446.8 |
| **11** | Thu | 85 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 581 | 446.7 |
| **12** | Fri | 84 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 581 | 446.7 |
| **13** | Mon | 81 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 684 | 403.8 |
| **14** | Tue | 80 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 784 | 409.8 |
| **16** | Thu | 78 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 856 | 420.5 |
| **17** | Fri | 77 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 856 | 420.5 |
| **18** | Mon | 74 | 0 | 대관령 | 18.6 | 0.700 | 116.2 | 336.1 | 18.4 | 986 | 475.7 |

## B09 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **611.3 KRW/kg** |
| Auction price, 3 days ago | 585.7 |
| Auction price, last 7-day mean | 602.6 |
| Auction grade spread | 0.779 |
| Auction volume (kg) | 471,150 |
| Wholesale / auction ratio | 1.175 |
| Wholesale price, yesterday | 733.3 |
| Wholesale price, 3 days ago | 733.3 |
| Wholesale price, 7 days ago | 733.3 |
| Wholesale price, 7-day mean | 733.3 |
| Wholesale price, 14-day mean | 728.6 |
| Wholesale price, 7-day std dev | 0 |
| Arrivals yesterday (tonnes) | 630 |
| Arrivals, 7-day mean (tonnes) | 849.4 |
| Retail price, yesterday | 1,926.7 |
| Temperature at the market city | 27 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 99 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 869.3 | 714.3 |
| **2** | Fri | 98 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 869.3 | 714.3 |
| **3** | Mon | 95 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 1,025.3 | 715.8 |
| **4** | Tue | 94 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 1,032 | 737.8 |
| **5** | Wed | 93 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 992 | 742.2 |
| **6** | Thu | 92 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 992 | 720 |
| **7** | Fri | 91 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 992 | 720 |
| **8** | Mon | 88 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 832 | 677.3 |
| **9** | Tue | 87 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 814.7 | 663.8 |
| **10** | Wed | 86 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 844 | 633.7 |
| **11** | Thu | 85 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 844 | 644.2 |
| **12** | Fri | 84 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 844 | 644.2 |
| **13** | Mon | 81 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 965.3 | 580.3 |
| **14** | Tue | 80 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 973.3 | 574.7 |
| **16** | Thu | 78 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 980 | 562.2 |
| **17** | Fri | 77 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 980 | 562.2 |
| **18** | Mon | 74 | 0 | 목포 | 24.4 | 0 | 71.2 | 492.1 | 23.1 | 1,008 | 624.5 |

## B10 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **406.1 KRW/kg** |
| Auction price, 3 days ago | 820.4 |
| Auction price, last 7-day mean | 459.8 |
| Auction grade spread | 1.782 |
| Auction volume (kg) | 366,790 |
| Wholesale / auction ratio | 2.642 |
| Wholesale price, yesterday | 860 |
| Wholesale price, 3 days ago | 860 |
| Wholesale price, 7 days ago | 860 |
| Wholesale price, 7-day mean | 860 |
| Wholesale price, 14-day mean | 868.6 |
| Wholesale price, 7-day std dev | 0 |
| Arrivals yesterday (tonnes) | 290 |
| Arrivals, 7-day mean (tonnes) | 349.4 |
| Retail price, yesterday | 3,837.5 |
| Temperature at the market city | 25.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 92 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 864 | 459 |
| **2** | Fri | 91 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 864 | 459 |
| **3** | Mon | 88 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 936 | 407.2 |
| **4** | Tue | 87 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 932 | 452.5 |
| **5** | Wed | 86 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 952 | 430.2 |
| **6** | Thu | 85 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 952 | 403.5 |
| **7** | Fri | 84 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 952 | 403.5 |
| **8** | Mon | 81 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,072 | 410.5 |
| **9** | Tue | 80 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,116 | 374.8 |
| **11** | Thu | 78 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,208 | 381 |
| **12** | Fri | 77 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,208 | 381 |
| **13** | Mon | 74 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,392 | 393.8 |
| **14** | Tue | 73 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,464 | 415.5 |
| **15** | Wed | 72 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,509 | 432 |
| **16** | Thu | 71 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,509 | 439.8 |
| **17** | Mon | 67 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,449 | 502.8 |
| **18** | Tue | 66 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 1,429 | 523.8 |

## B11 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **540.1 KRW/kg** |
| Auction price, 3 days ago | 513.1 |
| Auction price, last 7-day mean | 546.8 |
| Auction grade spread | 2.198 |
| Auction volume (kg) | 377,660 |
| Wholesale / auction ratio | 1.377 |
| Wholesale price, yesterday | 730 |
| Wholesale price, 3 days ago | 680 |
| Wholesale price, 7 days ago | 997.5 |
| Wholesale price, 7-day mean | 782.9 |
| Wholesale price, 14-day mean | 855.2 |
| Wholesale price, 7-day std dev | 147.9 |
| Arrivals yesterday (tonnes) | 345 |
| Arrivals, 7-day mean (tonnes) | 477.9 |
| Retail price, yesterday | 1,902.9 |
| Temperature at the market city | 25.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 92 | 0 | 고창군 | 22.9 | 35.4 | 86.1 | 430.2 | 24.2 | 694 | 463.3 |
| **2** | Fri | 91 | 0 | 고창군 | 22.9 | 35.4 | 86.1 | 430.2 | 24.2 | 694 | 463.3 |
| **3** | Mon | 88 | 0 | 고창군 | 22.9 | 35.4 | 86.1 | 430.2 | 24.2 | 669 | 449.5 |
| **4** | Tue | 87 | 0 | 고창군 | 22.9 | 35.4 | 86.1 | 430.2 | 24.2 | 606 | 473.8 |
| **5** | Wed | 86 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 581 | 446.8 |
| **6** | Thu | 85 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 581 | 446.7 |
| **7** | Fri | 84 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 581 | 446.7 |
| **8** | Mon | 81 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 684 | 403.8 |
| **9** | Tue | 80 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 784 | 409.8 |
| **11** | Thu | 78 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 856 | 420.5 |
| **12** | Fri | 77 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 856 | 420.5 |
| **13** | Mon | 74 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 986 | 475.7 |
| **14** | Tue | 73 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 961 | 495 |
| **15** | Wed | 72 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 974 | 448.5 |
| **16** | Thu | 71 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 974 | 446.5 |
| **17** | Mon | 67 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 869 | 496.2 |
| **18** | Tue | 66 | 0 | 대관령 | 14.7 | 87.3 | 108.8 | 358.8 | 19.3 | 816.5 | 492 |

## B12 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **645.9 KRW/kg** |
| Auction price, 3 days ago | 664.8 |
| Auction price, last 7-day mean | 645.1 |
| Auction grade spread | 0.917 |
| Auction volume (kg) | 490,185 |
| Wholesale / auction ratio | 1.133 |
| Wholesale price, yesterday | 733.3 |
| Wholesale price, 3 days ago | 733.3 |
| Wholesale price, 7 days ago | 733.3 |
| Wholesale price, 7-day mean | 733.3 |
| Wholesale price, 14-day mean | 733.3 |
| Wholesale price, 7-day std dev | 0 |
| Arrivals yesterday (tonnes) | 696 |
| Arrivals, 7-day mean (tonnes) | 773.7 |
| Retail price, yesterday | 1,913.3 |
| Temperature at the market city | 25.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 92 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 992 | 720 |
| **2** | Fri | 91 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 992 | 720 |
| **3** | Mon | 88 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 832 | 677.3 |
| **4** | Tue | 87 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 814.7 | 663.8 |
| **5** | Wed | 86 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 844 | 633.7 |
| **6** | Thu | 85 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 844 | 644.2 |
| **7** | Fri | 84 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 844 | 644.2 |
| **8** | Mon | 81 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 965.3 | 580.3 |
| **9** | Tue | 80 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 973.3 | 574.7 |
| **11** | Thu | 78 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 980 | 562.2 |
| **12** | Fri | 77 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 980 | 562.2 |
| **13** | Mon | 74 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,008 | 624.5 |
| **14** | Tue | 73 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,021.3 | 629.7 |
| **15** | Wed | 72 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,036 | 629.3 |
| **16** | Thu | 71 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,036 | 632.8 |
| **17** | Mon | 67 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,148 | 590.3 |
| **18** | Tue | 66 | 0 | 목포 | 22.3 | 44.2 | 77.6 | 512.6 | 24.1 | 1,184 | 615.2 |

## B13 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **372.7 KRW/kg** |
| Auction price, 3 days ago | 421.8 |
| Auction price, last 7-day mean | 388.0 |
| Auction grade spread | 1.659 |
| Auction volume (kg) | 343,840 |
| Wholesale / auction ratio | 2.402 |
| Wholesale price, yesterday | 840 |
| Wholesale price, 3 days ago | 860 |
| Wholesale price, 7 days ago | 860 |
| Wholesale price, 7-day mean | 854.3 |
| Wholesale price, 14-day mean | 854.3 |
| Wholesale price, 7-day std dev | 9.759 |
| Arrivals yesterday (tonnes) | 528 |
| Arrivals, 7-day mean (tonnes) | 391.4 |
| Retail price, yesterday | 3,882.5 |
| Temperature at the market city | 26.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 85 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 952 | 403.5 |
| **2** | Fri | 84 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 952 | 403.5 |
| **3** | Mon | 81 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,072 | 410.5 |
| **4** | Tue | 80 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,116 | 374.8 |
| **6** | Thu | 78 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,208 | 381 |
| **7** | Fri | 77 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,208 | 381 |
| **8** | Mon | 74 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,392 | 393.8 |
| **9** | Tue | 73 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,464 | 415.5 |
| **10** | Wed | 72 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,509 | 432 |
| **11** | Thu | 71 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,509 | 439.8 |
| **12** | Mon | 67 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,449 | 502.8 |
| **13** | Tue | 66 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,429 | 523.8 |
| **14** | Wed | 65 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,388 | 533.8 |
| **15** | Thu | 64 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,388 | 535.7 |
| **16** | Fri | 63 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,388 | 535.7 |
| **17** | Mon | 60 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,520 | 439.5 |
| **18** | Tue | 59 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 1,592 | 442.5 |

## B14 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **458.4 KRW/kg** |
| Auction price, 3 days ago | 407.8 |
| Auction price, last 7-day mean | 463.0 |
| Auction grade spread | 2.260 |
| Auction volume (kg) | 303,960 |
| Wholesale / auction ratio | 1.584 |
| Wholesale price, yesterday | 715 |
| Wholesale price, 3 days ago | 730 |
| Wholesale price, 7 days ago | 715 |
| Wholesale price, 7-day mean | 723.6 |
| Wholesale price, 14-day mean | 792.5 |
| Wholesale price, 7-day std dev | 8.018 |
| Arrivals yesterday (tonnes) | 367 |
| Arrivals, 7-day mean (tonnes) | 444.4 |
| Retail price, yesterday | 1,968.6 |
| Temperature at the market city | 26.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 85 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 581 | 446.7 |
| **2** | Fri | 84 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 581 | 446.7 |
| **3** | Mon | 81 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 684 | 403.8 |
| **4** | Tue | 80 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 784 | 409.8 |
| **6** | Thu | 78 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 856 | 420.5 |
| **7** | Fri | 77 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 856 | 420.5 |
| **8** | Mon | 74 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 986 | 475.7 |
| **9** | Tue | 73 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 961 | 495 |
| **10** | Wed | 72 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 974 | 448.5 |
| **11** | Thu | 71 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 974 | 446.5 |
| **12** | Mon | 67 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 869 | 496.2 |
| **13** | Tue | 66 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 816.5 | 492 |
| **14** | Wed | 65 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 751.5 | 515.8 |
| **15** | Thu | 64 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 751.5 | 523 |
| **16** | Fri | 63 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 751.5 | 523 |
| **17** | Mon | 60 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 705 | 516.2 |
| **18** | Tue | 59 | 0 | 대관령 | 18.6 | 13.9 | 120.8 | 350.7 | 19.6 | 730.5 | 536.5 |

## B15 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **784.9 KRW/kg** |
| Auction price, 3 days ago | 784.3 |
| Auction price, last 7-day mean | 758.0 |
| Auction grade spread | 0.792 |
| Auction volume (kg) | 493,620 |
| Wholesale / auction ratio | 0.953 |
| Wholesale price, yesterday | 786.7 |
| Wholesale price, 3 days ago | 733.3 |
| Wholesale price, 7 days ago | 733.3 |
| Wholesale price, 7-day mean | 748.6 |
| Wholesale price, 14-day mean | 741.0 |
| Wholesale price, 7-day std dev | 26.0 |
| Arrivals yesterday (tonnes) | 758 |
| Arrivals, 7-day mean (tonnes) | 646.6 |
| Retail price, yesterday | 1,764.7 |
| Temperature at the market city | 26.8 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Thu | 85 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 844 | 644.2 |
| **2** | Fri | 84 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 844 | 644.2 |
| **3** | Mon | 81 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 965.3 | 580.3 |
| **4** | Tue | 80 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 973.3 | 574.7 |
| **6** | Thu | 78 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 980 | 562.2 |
| **7** | Fri | 77 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 980 | 562.2 |
| **8** | Mon | 74 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,008 | 624.5 |
| **9** | Tue | 73 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,021.3 | 629.7 |
| **10** | Wed | 72 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,036 | 629.3 |
| **11** | Thu | 71 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,036 | 632.8 |
| **12** | Mon | 67 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,148 | 590.3 |
| **13** | Tue | 66 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,184 | 615.2 |
| **14** | Wed | 65 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,220 | 639.5 |
| **15** | Thu | 64 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,220 | 656 |
| **16** | Fri | 63 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,220 | 656 |
| **17** | Mon | 60 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,220 | 667.2 |
| **18** | Tue | 59 | 0 | 목포 | 24.4 | 0 | 68 | 523.1 | 25.2 | 1,220 | 660.7 |

## B16 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **507.2 KRW/kg** |
| Auction price, 3 days ago | 313.2 |
| Auction price, last 7-day mean | 410.8 |
| Auction grade spread | 1.227 |
| Auction volume (kg) | 326,950 |
| Wholesale / auction ratio | 1.350 |
| Wholesale price, yesterday | 880 |
| Wholesale price, 3 days ago | 840 |
| Wholesale price, 7 days ago | 840 |
| Wholesale price, 7-day mean | 851.4 |
| Wholesale price, 14-day mean | 854.3 |
| Wholesale price, 7-day std dev | 19.5 |
| Arrivals yesterday (tonnes) | 358 |
| Arrivals, 7-day mean (tonnes) | 407.3 |
| Retail price, yesterday | 3,562.5 |
| Temperature at the market city | 25.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Fri | 77 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,208 | 381 |
| **2** | Mon | 74 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,392 | 393.8 |
| **3** | Tue | 73 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,464 | 415.5 |
| **4** | Wed | 72 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,509 | 432 |
| **5** | Thu | 71 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,509 | 439.8 |
| **6** | Mon | 67 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,449 | 502.8 |
| **7** | Tue | 66 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,429 | 523.8 |
| **8** | Wed | 65 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,388 | 533.8 |
| **9** | Thu | 64 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,388 | 535.7 |
| **10** | Fri | 63 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,388 | 535.7 |
| **11** | Mon | 60 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,520 | 439.5 |
| **12** | Tue | 59 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,592 | 442.5 |
| **13** | Wed | 58 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,692 | 441.5 |
| **14** | Thu | 57 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,692 | 451 |
| **15** | Fri | 56 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 1,692 | 451 |
| **16** | Mon | 53 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 2,112 | 468 |
| **17** | Tue | 52 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 2,188 | 438 |
| **18** | Wed | 51 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 2,272 | 444.2 |

## B17 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **580.2 KRW/kg** |
| Auction price, 3 days ago | 613.0 |
| Auction price, last 7-day mean | 566.8 |
| Auction grade spread | 1.391 |
| Auction volume (kg) | 540,560 |
| Wholesale / auction ratio | 1.250 |
| Wholesale price, yesterday | 750 |
| Wholesale price, 3 days ago | 715 |
| Wholesale price, 7 days ago | 715 |
| Wholesale price, 7-day mean | 725 |
| Wholesale price, 14-day mean | 721.8 |
| Wholesale price, 7-day std dev | 17.1 |
| Arrivals yesterday (tonnes) | 667 |
| Arrivals, 7-day mean (tonnes) | 440.3 |
| Retail price, yesterday | 1,920 |
| Temperature at the market city | 25.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Fri | 77 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 856 | 420.5 |
| **2** | Mon | 74 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 986 | 475.7 |
| **3** | Tue | 73 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 961 | 495 |
| **4** | Wed | 72 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 974 | 448.5 |
| **5** | Thu | 71 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 974 | 446.5 |
| **6** | Mon | 67 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 869 | 496.2 |
| **7** | Tue | 66 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 816.5 | 492 |
| **8** | Wed | 65 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 751.5 | 515.8 |
| **9** | Thu | 64 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 751.5 | 523 |
| **10** | Fri | 63 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 751.5 | 523 |
| **11** | Mon | 60 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 705 | 516.2 |
| **12** | Tue | 59 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 730.5 | 536.5 |
| **13** | Wed | 58 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 775.5 | 539.3 |
| **14** | Thu | 57 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 775.5 | 561.2 |
| **15** | Fri | 56 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 775.5 | 561.2 |
| **16** | Mon | 53 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 930 | 537.8 |
| **17** | Tue | 52 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 937 | 522.8 |
| **18** | Wed | 51 | 0 | 대관령 | 21 | 30.9 | 132.8 | 384.9 | 20.2 | 927 | 531.6 |

## B18 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **983.6 KRW/kg** |
| Auction price, 3 days ago | 803.4 |
| Auction price, last 7-day mean | 887.4 |
| Auction grade spread | 0.922 |
| Auction volume (kg) | 457,020 |
| Wholesale / auction ratio | 0.975 |
| Wholesale price, yesterday | 1,100 |
| Wholesale price, 3 days ago | 1,006.7 |
| Wholesale price, 7 days ago | 786.7 |
| Wholesale price, 7-day mean | 917.1 |
| Wholesale price, 14-day mean | 829.0 |
| Wholesale price, 7-day std dev | 146.4 |
| Arrivals yesterday (tonnes) | 867 |
| Arrivals, 7-day mean (tonnes) | 702.4 |
| Retail price, yesterday | 1,794.7 |
| Temperature at the market city | 25.1 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Fri | 77 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 980 | 562.2 |
| **2** | Mon | 74 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,008 | 624.5 |
| **3** | Tue | 73 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,021.3 | 629.7 |
| **4** | Wed | 72 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,036 | 629.3 |
| **5** | Thu | 71 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,036 | 632.8 |
| **6** | Mon | 67 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,148 | 590.3 |
| **7** | Tue | 66 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,184 | 615.2 |
| **8** | Wed | 65 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 639.5 |
| **9** | Thu | 64 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 656 |
| **10** | Fri | 63 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 656 |
| **11** | Mon | 60 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 667.2 |
| **12** | Tue | 59 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 660.7 |
| **13** | Wed | 58 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 632.5 |
| **14** | Thu | 57 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 643.6 |
| **15** | Fri | 56 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 643.6 |
| **16** | Mon | 53 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 700.4 |
| **17** | Tue | 52 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 663 |
| **18** | Wed | 51 | 0 | 목포 | 25.8 | 15.4 | 115.9 | 544.1 | 25.4 | 1,220 | 697 |

## B19 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **451.6 KRW/kg** |
| Auction price, 3 days ago | 331.7 |
| Auction price, last 7-day mean | 466.2 |
| Auction grade spread | 2.118 |
| Auction volume (kg) | 326,990 |
| Wholesale / auction ratio | 2.193 |
| Wholesale price, yesterday | 942.5 |
| Wholesale price, 3 days ago | 920 |
| Wholesale price, 7 days ago | 880 |
| Wholesale price, 7-day mean | 906.1 |
| Wholesale price, 14-day mean | 874.5 |
| Wholesale price, 7-day std dev | 25.7 |
| Arrivals yesterday (tonnes) | 418 |
| Arrivals, 7-day mean (tonnes) | 526.5 |
| Retail price, yesterday | 3,451.2 |
| Temperature at the market city | 24.6 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Mon | 67 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,449 | 502.8 |
| **2** | Tue | 66 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,429 | 523.8 |
| **3** | Wed | 65 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,388 | 533.8 |
| **4** | Thu | 64 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,388 | 535.7 |
| **5** | Fri | 63 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,388 | 535.7 |
| **6** | Mon | 60 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,520 | 439.5 |
| **7** | Tue | 59 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,592 | 442.5 |
| **8** | Wed | 58 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,692 | 441.5 |
| **9** | Thu | 57 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,692 | 451 |
| **10** | Fri | 56 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 1,692 | 451 |
| **11** | Mon | 53 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,112 | 468 |
| **12** | Tue | 52 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,188 | 438 |
| **13** | Wed | 51 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,272 | 444.2 |
| **14** | Thu | 50 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,272 | 436.8 |
| **15** | Fri | 49 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,272 | 436.8 |
| **16** | Mon | 46 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,084 | 502 |
| **17** | Tue | 45 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,100 | 488.5 |
| **18** | Wed | 44 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 2,040 | 474.2 |

## B20 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **505.4 KRW/kg** |
| Auction price, 3 days ago | 481.2 |
| Auction price, last 7-day mean | 496.8 |
| Auction grade spread | 1.804 |
| Auction volume (kg) | 409,320 |
| Wholesale / auction ratio | 1.447 |
| Wholesale price, yesterday | 750 |
| Wholesale price, 3 days ago | 750 |
| Wholesale price, 7 days ago | 750 |
| Wholesale price, 7-day mean | 750 |
| Wholesale price, 14-day mean | 733.6 |
| Wholesale price, 7-day std dev | 0 |
| Arrivals yesterday (tonnes) | 428 |
| Arrivals, 7-day mean (tonnes) | 516.5 |
| Retail price, yesterday | 2,067.1 |
| Temperature at the market city | 24.6 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Mon | 67 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 869 | 496.2 |
| **2** | Tue | 66 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 816.5 | 492 |
| **3** | Wed | 65 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 751.5 | 515.8 |
| **4** | Thu | 64 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 751.5 | 523 |
| **5** | Fri | 63 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 751.5 | 523 |
| **6** | Mon | 60 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 705 | 516.2 |
| **7** | Tue | 59 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 730.5 | 536.5 |
| **8** | Wed | 58 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 775.5 | 539.3 |
| **9** | Thu | 57 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 775.5 | 561.2 |
| **10** | Fri | 56 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 775.5 | 561.2 |
| **11** | Mon | 53 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 930 | 537.8 |
| **12** | Tue | 52 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 937 | 522.8 |
| **13** | Wed | 51 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 927 | 531.6 |
| **14** | Thu | 50 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 927 | 529 |
| **15** | Fri | 49 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 927 | 529 |
| **16** | Mon | 46 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 819 | 526.5 |
| **17** | Tue | 45 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 834 | 521 |
| **18** | Wed | 44 | 0 | 대관령 | 22.9 | 35.1 | 167.2 | 439.9 | 21.7 | 830 | 484 |

## B21 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **894.3 KRW/kg** |
| Auction price, 3 days ago | 895.5 |
| Auction price, last 7-day mean | 924.5 |
| Auction grade spread | 1.217 |
| Auction volume (kg) | 287,265 |
| Wholesale / auction ratio | 1.343 |
| Wholesale price, yesterday | 1,140 |
| Wholesale price, 3 days ago | 1,073.3 |
| Wholesale price, 7 days ago | 1,100 |
| Wholesale price, 7-day mean | 1,094.3 |
| Wholesale price, 14-day mean | 957.1 |
| Wholesale price, 7-day std dev | 24.2 |
| Arrivals yesterday (tonnes) | 540 |
| Arrivals, 7-day mean (tonnes) | 718.8 |
| Retail price, yesterday | 1,537.4 |
| Temperature at the market city | 24.6 |
| Market closed yesterday (1=yes) | 0 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Mon | 67 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,148 | 590.3 |
| **2** | Tue | 66 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,184 | 615.2 |
| **3** | Wed | 65 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 639.5 |
| **4** | Thu | 64 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 656 |
| **5** | Fri | 63 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 656 |
| **6** | Mon | 60 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 667.2 |
| **7** | Tue | 59 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 660.7 |
| **8** | Wed | 58 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 632.5 |
| **9** | Thu | 57 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 643.6 |
| **10** | Fri | 56 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 643.6 |
| **11** | Mon | 53 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 700.4 |
| **12** | Tue | 52 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 663 |
| **13** | Wed | 51 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 697 |
| **14** | Thu | 50 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 678 |
| **15** | Fri | 49 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 678 |
| **16** | Mon | 46 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 644 |
| **17** | Tue | 45 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 665.3 |
| **18** | Wed | 44 | 0 | 목포 | 27.3 | 3.800 | 119.7 | 583.1 | 26.6 | 1,220 | 645.2 |

## B22 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **655.1 KRW/kg** |
| Auction price, 3 days ago | 302.3 |
| Auction price, last 7-day mean | 532.1 |
| Auction grade spread | 1.417 |
| Auction volume (kg) | 209,530 |
| Wholesale / auction ratio | 1.286 |
| Wholesale price, yesterday | 1,080 |
| Wholesale price, 3 days ago | 1,040 |
| Wholesale price, 7 days ago | 942.5 |
| Wholesale price, 7-day mean | 1,034.6 |
| Wholesale price, 14-day mean | 963.0 |
| Wholesale price, 7-day std dev | 43.4 |
| Arrivals yesterday (tonnes) | 256 |
| Arrivals, 7-day mean (tonnes) | 395 |
| Retail price, yesterday | 3,902.5 |
| Temperature at the market city | 29.2 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 59 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,592 | 442.5 |
| **2** | Wed | 58 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,692 | 441.5 |
| **3** | Thu | 57 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,692 | 451 |
| **4** | Fri | 56 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,692 | 451 |
| **5** | Mon | 53 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,112 | 468 |
| **6** | Tue | 52 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,188 | 438 |
| **7** | Wed | 51 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,272 | 444.2 |
| **8** | Thu | 50 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,272 | 436.8 |
| **9** | Fri | 49 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,272 | 436.8 |
| **10** | Mon | 46 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,084 | 502 |
| **11** | Tue | 45 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,100 | 488.5 |
| **12** | Wed | 44 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,040 | 474.2 |
| **13** | Thu | 43 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,040 | 464.2 |
| **14** | Fri | 42 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 2,040 | 464.2 |
| **15** | Tue | 38 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,930 | 455.7 |
| **16** | Wed | 37 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,928 | 464.3 |
| **17** | Thu | 36 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,928 | 484 |
| **18** | Fri | 35 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 1,928 | 484 |

## B23 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **370.6 KRW/kg** |
| Auction price, 3 days ago | 270.3 |
| Auction price, last 7-day mean | 357.9 |
| Auction grade spread | 1.758 |
| Auction volume (kg) | 289,800 |
| Wholesale / auction ratio | 1.643 |
| Wholesale price, yesterday | 640 |
| Wholesale price, 3 days ago | 750 |
| Wholesale price, 7 days ago | 750 |
| Wholesale price, 7-day mean | 718.6 |
| Wholesale price, 14-day mean | 731.8 |
| Wholesale price, 7-day std dev | 53.7 |
| Arrivals yesterday (tonnes) | 367 |
| Arrivals, 7-day mean (tonnes) | 501.6 |
| Retail price, yesterday | 1,975.2 |
| Temperature at the market city | 29.2 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 59 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 730.5 | 536.5 |
| **2** | Wed | 58 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 775.5 | 539.3 |
| **3** | Thu | 57 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 775.5 | 561.2 |
| **4** | Fri | 56 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 775.5 | 561.2 |
| **5** | Mon | 53 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 930 | 537.8 |
| **6** | Tue | 52 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 937 | 522.8 |
| **7** | Wed | 51 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 927 | 531.6 |
| **8** | Thu | 50 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 927 | 529 |
| **9** | Fri | 49 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 927 | 529 |
| **10** | Mon | 46 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 819 | 526.5 |
| **11** | Tue | 45 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 834 | 521 |
| **12** | Wed | 44 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 830 | 484 |
| **13** | Thu | 43 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 830 | 446.8 |
| **14** | Fri | 42 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 830 | 446.8 |
| **15** | Tue | 38 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 735 | 492.3 |
| **16** | Wed | 37 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 730 | 551.5 |
| **17** | Thu | 36 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 730 | 576 |
| **18** | Fri | 35 | 0 | 대관령 | 23.4 | 53 | 205.4 | 499.9 | 23.0 | 730 | 576 |

## B24 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **1,069.9 KRW/kg** |
| Auction price, 3 days ago | 998.0 |
| Auction price, last 7-day mean | 1,043.2 |
| Auction grade spread | 1.111 |
| Auction volume (kg) | 434,655 |
| Wholesale / auction ratio | 1.099 |
| Wholesale price, yesterday | 1,220 |
| Wholesale price, 3 days ago | 1,140 |
| Wholesale price, 7 days ago | 1,140 |
| Wholesale price, 7-day mean | 1,162.9 |
| Wholesale price, 14-day mean | 1,119.0 |
| Wholesale price, 7-day std dev | 39.0 |
| Arrivals yesterday (tonnes) | 825 |
| Arrivals, 7-day mean (tonnes) | 921.3 |
| Retail price, yesterday | 1,668.9 |
| Temperature at the market city | 29.2 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 59 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 660.7 |
| **2** | Wed | 58 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 632.5 |
| **3** | Thu | 57 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 643.6 |
| **4** | Fri | 56 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 643.6 |
| **5** | Mon | 53 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 700.4 |
| **6** | Tue | 52 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 663 |
| **7** | Wed | 51 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 697 |
| **8** | Thu | 50 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 678 |
| **9** | Fri | 49 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 678 |
| **10** | Mon | 46 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 644 |
| **11** | Tue | 45 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 665.3 |
| **12** | Wed | 44 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 645.2 |
| **13** | Thu | 43 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 644.2 |
| **14** | Fri | 42 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 644.2 |
| **15** | Tue | 38 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 701.7 |
| **16** | Wed | 37 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 704.3 |
| **17** | Thu | 36 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 687.8 |
| **18** | Fri | 35 | 0 | 목포 | 29.2 | 1.600 | 134.8 | 638.9 | 28.6 | 1,220 | 687.8 |

## B25 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **725.4 KRW/kg** |
| Auction price, 3 days ago | 888.1 |
| Auction price, last 7-day mean | 729.4 |
| Auction grade spread | 1.710 |
| Auction volume (kg) | 319,140 |
| Wholesale / auction ratio | 1.668 |
| Wholesale price, yesterday | 1,200 |
| Wholesale price, 3 days ago | 1,200 |
| Wholesale price, 7 days ago | 1,060 |
| Wholesale price, 7-day mean | 1,145.7 |
| Wholesale price, 14-day mean | 1,068.8 |
| Wholesale price, 7-day std dev | 68.0 |
| Arrivals yesterday (tonnes) | 404 |
| Arrivals, 7-day mean (tonnes) | 398.6 |
| Retail price, yesterday | 4,055.7 |
| Temperature at the market city | 30.4 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 52 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,188 | 438 |
| **2** | Wed | 51 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,272 | 444.2 |
| **3** | Thu | 50 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,272 | 436.8 |
| **4** | Fri | 49 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,272 | 436.8 |
| **5** | Mon | 46 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,084 | 502 |
| **6** | Tue | 45 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,100 | 488.5 |
| **7** | Wed | 44 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,040 | 474.2 |
| **8** | Thu | 43 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,040 | 464.2 |
| **9** | Fri | 42 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,040 | 464.2 |
| **10** | Tue | 38 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 1,930 | 455.7 |
| **11** | Wed | 37 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 1,928 | 464.3 |
| **12** | Thu | 36 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 1,928 | 484 |
| **13** | Fri | 35 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 1,928 | 484 |
| **14** | Mon | 32 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 1,928 | 479.8 |
| **15** | Tue | 31 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,064 | 469.2 |
| **16** | Wed | 30 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,200 | 491.3 |
| **17** | Thu | 29 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 2,200 | 501 |

## B26 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **410.8 KRW/kg** |
| Auction price, 3 days ago | 260.7 |
| Auction price, last 7-day mean | 368.5 |
| Auction grade spread | 0.770 |
| Auction volume (kg) | 348,500 |
| Wholesale / auction ratio | 1.265 |
| Wholesale price, yesterday | 600 |
| Wholesale price, 3 days ago | 600 |
| Wholesale price, 7 days ago | 640 |
| Wholesale price, 7-day mean | 617.1 |
| Wholesale price, 14-day mean | 683.6 |
| Wholesale price, 7-day std dev | 21.4 |
| Arrivals yesterday (tonnes) | 437 |
| Arrivals, 7-day mean (tonnes) | 512 |
| Retail price, yesterday | 1,664 |
| Temperature at the market city | 30.4 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 52 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 937 | 522.8 |
| **2** | Wed | 51 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 927 | 531.6 |
| **3** | Thu | 50 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 927 | 529 |
| **4** | Fri | 49 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 927 | 529 |
| **5** | Mon | 46 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 819 | 526.5 |
| **6** | Tue | 45 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 834 | 521 |
| **7** | Wed | 44 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 830 | 484 |
| **8** | Thu | 43 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 830 | 446.8 |
| **9** | Fri | 42 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 830 | 446.8 |
| **10** | Tue | 38 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 735 | 492.3 |
| **11** | Wed | 37 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 730 | 551.5 |
| **12** | Thu | 36 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 730 | 576 |
| **13** | Fri | 35 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 730 | 576 |
| **14** | Mon | 32 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 794 | 516.5 |
| **15** | Tue | 31 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 832 | 488.3 |
| **16** | Wed | 30 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 870 | 472 |
| **17** | Thu | 29 | 0 | 대관령 | 25.6 | 3.200 | 203.8 | 547.6 | 22.0 | 870 | 481 |

## B27 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **1,110.8 KRW/kg** |
| Auction price, 3 days ago | 1,197.1 |
| Auction price, last 7-day mean | 1,122.9 |
| Auction grade spread | 0.934 |
| Auction volume (kg) | 448,020 |
| Wholesale / auction ratio | 1.159 |
| Wholesale price, yesterday | 1,266.7 |
| Wholesale price, 3 days ago | 1,266.7 |
| Wholesale price, 7 days ago | 1,220 |
| Wholesale price, 7-day mean | 1,246.7 |
| Wholesale price, 14-day mean | 1,183.8 |
| Wholesale price, 7-day std dev | 24.9 |
| Arrivals yesterday (tonnes) | 715 |
| Arrivals, 7-day mean (tonnes) | 787.3 |
| Retail price, yesterday | 1,947.8 |
| Temperature at the market city | 30.4 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 52 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 663 |
| **2** | Wed | 51 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 697 |
| **3** | Thu | 50 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 678 |
| **4** | Fri | 49 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 678 |
| **5** | Mon | 46 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 644 |
| **6** | Tue | 45 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 665.3 |
| **7** | Wed | 44 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 645.2 |
| **8** | Thu | 43 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 644.2 |
| **9** | Fri | 42 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 644.2 |
| **10** | Tue | 38 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 701.7 |
| **11** | Wed | 37 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 704.3 |
| **12** | Thu | 36 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 687.8 |
| **13** | Fri | 35 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 687.8 |
| **14** | Mon | 32 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 584.3 |
| **15** | Tue | 31 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 579.5 |
| **16** | Wed | 30 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 585.5 |
| **17** | Thu | 29 | 0 | 목포 | 28.9 | 0 | 78.5 | 676.8 | 28.2 | 1,220 | 580.8 |

## B28 - item **napa cabbage (배추)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **751.2 KRW/kg** |
| Auction price, 3 days ago | 595.3 |
| Auction price, last 7-day mean | 714.3 |
| Auction grade spread | 1.922 |
| Auction volume (kg) | 263,290 |
| Wholesale / auction ratio | 1.637 |
| Wholesale price, yesterday | 1,320 |
| Wholesale price, 3 days ago | 1,280 |
| Wholesale price, 7 days ago | 1,200 |
| Wholesale price, 7-day mean | 1,262.9 |
| Wholesale price, 14-day mean | 1,181.4 |
| Wholesale price, 7-day std dev | 45.4 |
| Arrivals yesterday (tonnes) | 323 |
| Arrivals, 7-day mean (tonnes) | 399.2 |
| Retail price, yesterday | 4,332.5 |
| Temperature at the market city | 27.6 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 45 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,100 | 488.5 |
| **2** | Wed | 44 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,040 | 474.2 |
| **3** | Thu | 43 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,040 | 464.2 |
| **4** | Fri | 42 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,040 | 464.2 |
| **5** | Tue | 38 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 1,930 | 455.7 |
| **6** | Wed | 37 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 1,928 | 464.3 |
| **7** | Thu | 36 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 1,928 | 484 |
| **8** | Fri | 35 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 1,928 | 484 |
| **9** | Mon | 32 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 1,928 | 479.8 |
| **10** | Tue | 31 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,064 | 469.2 |
| **11** | Wed | 30 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,200 | 491.3 |
| **12** | Thu | 29 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 2,200 | 501 |

## B29 - item **Korean radish (무)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **607.3 KRW/kg** |
| Auction price, 3 days ago | 443.3 |
| Auction price, last 7-day mean | 527.8 |
| Auction grade spread | 1.053 |
| Auction volume (kg) | 342,660 |
| Wholesale / auction ratio | 1.073 |
| Wholesale price, yesterday | 780 |
| Wholesale price, 3 days ago | 680 |
| Wholesale price, 7 days ago | 600 |
| Wholesale price, 7-day mean | 667.1 |
| Wholesale price, 14-day mean | 663.6 |
| Wholesale price, 7-day std dev | 64.0 |
| Arrivals yesterday (tonnes) | 425 |
| Arrivals, 7-day mean (tonnes) | 511.5 |
| Retail price, yesterday | 1,796.9 |
| Temperature at the market city | 27.6 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 45 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 834 | 521 |
| **2** | Wed | 44 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 830 | 484 |
| **3** | Thu | 43 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 830 | 446.8 |
| **4** | Fri | 42 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 830 | 446.8 |
| **5** | Tue | 38 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 735 | 492.3 |
| **6** | Wed | 37 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 730 | 551.5 |
| **7** | Thu | 36 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 730 | 576 |
| **8** | Fri | 35 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 730 | 576 |
| **9** | Mon | 32 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 794 | 516.5 |
| **10** | Tue | 31 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 832 | 488.3 |
| **11** | Wed | 30 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 870 | 472 |
| **12** | Thu | 29 | 0 | 대관령 | 18.9 | 42.1 | 199.8 | 553.7 | 21.0 | 870 | 481 |

## B30 - item **onion (양파)**

### Values fixed within this block

| Item | Value |
|---|---|
| **Starting point (40% yesterday + 60% last-7-day mean)** | **1,137.7 KRW/kg** |
| Auction price, 3 days ago | 1,091.8 |
| Auction price, last 7-day mean | 1,128.7 |
| Auction grade spread | 0.857 |
| Auction volume (kg) | 408,630 |
| Wholesale / auction ratio | 1.071 |
| Wholesale price, yesterday | 1,233.3 |
| Wholesale price, 3 days ago | 1,240 |
| Wholesale price, 7 days ago | 1,266.7 |
| Wholesale price, 7-day mean | 1,248.6 |
| Wholesale price, 14-day mean | 1,229.5 |
| Wholesale price, 7-day std dev | 13.7 |
| Arrivals yesterday (tonnes) | 765 |
| Arrivals, 7-day mean (tonnes) | 951.8 |
| Retail price, yesterday | 1,844.4 |
| Temperature at the market city | 27.6 |
| Market closed yesterday (1=yes) | 1 |

### Values that change by horizon

| Days ahead | Weekday of target day | Days until the next holiday | Kimjang season (1=yes) | Main growing-area station | Growing-area temperature | Growing-area rain, 7 days | Growing-area rain, 30 days | Growing-area growing-degree-days, 30 days | Growing-area normal temperature | Wholesale price, same period last year | Arrivals, same period last year |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **1** | Tue | 45 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 665.3 |
| **2** | Wed | 44 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 645.2 |
| **3** | Thu | 43 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 644.2 |
| **4** | Fri | 42 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 644.2 |
| **5** | Tue | 38 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 701.7 |
| **6** | Wed | 37 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 704.3 |
| **7** | Thu | 36 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 687.8 |
| **8** | Fri | 35 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 687.8 |
| **9** | Mon | 32 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 584.3 |
| **10** | Tue | 31 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 579.5 |
| **11** | Wed | 30 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 585.5 |
| **12** | Thu | 29 | 0 | 목포 | 29.8 | 12.3 | 71.6 | 707 | 27.4 | 1,220 | 580.8 |

---

**이제 30줄을 출력하세요. 설명 없이 `블록번호|숫자18개` 형식만.**
