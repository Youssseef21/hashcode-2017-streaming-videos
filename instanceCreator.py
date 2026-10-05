import numpy as np
from collections.abc import Callable
from typing import Literal

# LIMITATION OF THE INSTANCE PARAMETERS (system)
## Videos
MAX_AUTHORISED_VIDEO_NUMBER = 10000
MAX_AUTHORISED_VIDEO_SIZE = 1000

## Cache
MAX_AUTHORISED_CACHE_NUMBER = 1000
MAX_AUTHORISED_CACHE_CAPACITY = 500000
MAX_AUTHORISED_CACHE_LATENCY = 500

## Endpoint
MAX_AUTHORISED_ENDPOINT_NUMBER = 1000
MIN_AUTHORISED_SERVER_LATENCY = 2
MAX_AUTHORISED_SERVER_LATENCY = 4000
MAX_AUTHORISED_REQUEST_PER_ENDPOINT = 10000

## Request
MAX_AUTHORISED_REQUEST_NUMBER = 1000000


# Generators
## Utils
generator = {}
def registerGenerator(func:Callable) -> Callable:
    """Decorator to register a function in the generator.

    Args:
        func (Callable): An arbitrary function.

    Returns:
        Callable: The initial function.
    """
    generator[func.__name__] = func
    return func

def generatorToString(E:int, C:int, X:int, videos:list[int], requests:dict[int,tuple[list[int], list[int]]], connected_caches:dict[int,tuple[list[int], list[int], list[int]]]) -> str:
    """Global function to transform variables of a generator to the string of a valid instance

    Args:
        E (int): Number of Endpoint
        C (int): Number of caches
        X (int): Memory of caches
        videos (list[int]): list of the size of each video. (ex: [10,234,28])
        requests (dict[int,tuple[list[int], list[int]]]): Dictionary organizing requests per endpoints (ex: {0:([10,4],([1040,2500]), 1:([10,10],[1200,700]))} -> the endpoint 0 request 1040 times video 10, 2500 times video 4, video 1 request twice video 10 with 1200 count and 700 count.)
        connected_caches (dict[int,tuple[int, list[int], list[int]]]): Dictionary organizing the connection of an endpoint (ex: {0:(100,[10,3],[50,40]), 1:(207,[1],[200])} -> endpoint 0 is connected to dc with 100ms, to c10 with 10ms, c3 with 40ms, e1 to dc with 207ms, c1 with 200ms.)

    Returns:
        str: The string of a valid instance from the provided informations
    """
    # Compute the number of requests from the dictionary of request per endpoint 
    R = sum([len(requests[idE][0]) for idE in range(E)])
    
    # Add instance parameter
    string = f"{len(videos)} {E} {R} {C} {X}\n"
    
    # Add all video size
    string += " ".join(list(map(lambda x: f"{x}", videos))) + "\n"
    
    # For each endpoints
    for endpoint in range(E):
        # Add the endpoint datacenter latency and the number of connected caches
        string += f"{connected_caches[endpoint][0]} {len(connected_caches[endpoint][1])}\n"
        
        # For each connected cache
        for idC, cache in enumerate(connected_caches[endpoint][1]):
            # Get the cache and the corresponding latency
            string += f"{cache} {connected_caches[endpoint][2][idC]}\n"
    
    # For each endpoint, get their requests
    for endpoint, req in requests.items():
        # For each request
        for r in range(len(req[0])):
            # Mark the video id, the endpoint and the count requested
            string += f"{req[0][r]} {endpoint} {req[1][r]}\n"

    return string.strip()

## DéjàVu
@registerGenerator
def dejaVu(E:int=115, V:int=10_000, R:int=999_950, V_min_size:int=4, V_max_size:int=110, C:int=20, X:int=2000, seed:int=42, **kwargs) -> str:
    """Function to generate instance whose endpoints request intrinsic kernel of video, which is duplicated to match average noised request per endpoint.  

    Args:
        E (int, optional): Number of endpoints. Defaults to 115.
        V (int, optional): Number of videos. Defaults to 10_000.
        R (int, optional): Number of requests. Defaults to 999_950.
        V_min_size (int, optional): Minimum size of video. Defaults to 4.
        V_max_size (int, optional): Maximum size of video. Defaults to 110.
        C (int, optional): Number of cache. Defaults to 20.
        X (int, optional): Size of a cache. Defaults to 2000.
        seed (int, optional): Random seed for noise and global generation. Defaults to 42.

    Returns:
        str: An instance
    """
    # Fixed parameter of this generator
    CACHE_CONNECTIONS = 4
    UNIQUE_REQUEST_PROP = 0.075
    COUNT_MIN = 2
    COUNT_MAX = 12783
    LOCAL_MAX_CACHE_LATENCY = 1000
    
    # Initialise a random number generator
    rng = np.random.RandomState(seed)
    
    # Number of video per endpoint
    re = R//E
    requestPerEndpoint = np.full(E, re, dtype=int)
    
    # Add noise to request st the number of request per endpoint is stable
    noise = rng.randint(0.9*re, 1.1*re, size=E)
    noise = noise - int(noise.mean())
    noisedRequestPerEndpoint = requestPerEndpoint + noise
    
    # Videos
    videos = rng.randint(V_min_size, V_max_size, size=V).tolist()
    
    # Get unique requests number for each endpoint, then generate the list of video id serving as kernel of this method for each endpoint
    uniqueRequestNumber = (UNIQUE_REQUEST_PROP*noisedRequestPerEndpoint).astype(int)
    uniqueVideoIDs = [rng.randint(0, V, urn).tolist() for urn in uniqueRequestNumber]
    
    # Request and connected cache generation
    endpointRequestDict = {}
    connectedCachesDict = {}
    
    # Generate datacenter latencies randomly for each endpoint
    endpoint2DataCenterLatency = rng.randint(MIN_AUTHORISED_SERVER_LATENCY, LOCAL_MAX_CACHE_LATENCY, size=E)
    
    # For each endpoint, get their video kernel
    for idEndpoint, v in enumerate(uniqueVideoIDs):
        # Organize connected cache by adding latency to datacenter, connected caches and their corresponding latencies
        connectedCachesDict[idEndpoint] = (
            endpoint2DataCenterLatency[idEndpoint], # Latency to datacenter
            rng.choice(np.arange(C), size=CACHE_CONNECTIONS, replace=False).tolist(), # Connected caches
            rng.randint(1, min(MAX_AUTHORISED_CACHE_LATENCY, endpoint2DataCenterLatency[idEndpoint]), size=CACHE_CONNECTIONS).tolist() # Corresponding latency
        )
        
        # Organize requests for each endpoint by expanding the kernel of video to match the required number of videos as well as the count of request
        endpointRequestDict[idEndpoint] = (
            rng.choice(v, noisedRequestPerEndpoint[idEndpoint], replace=True).tolist(), # Requested Videos
            rng.randint(COUNT_MIN, COUNT_MAX, noisedRequestPerEndpoint[idEndpoint]).tolist() # Count of request
        )
    
    # Generate the corresponding string
    return generatorToString(E, C, X, videos, endpointRequestDict, connectedCachesDict)

@registerGenerator
def universalLambda(E:int, V:int, C:int, X:int, videoSizeLambda:Callable, requestLambda:Callable, dcLambda:Callable, connectionLambda:Callable, seed:int=42, **kwargs) -> str:
    """Function to generate instance whose parameter are designed using function over id. It is, in a way, an universal generator bounded only to the imagination of the user.
    Disclaimer, since the generator is fully opened to the user input, we cannot warranty any validity of the instance. Hence, it should be checked with a validator.

    Args:
        E (int): Number of endpoints
        V (int): Number of videos
        C (int): Number of caches
        X (int): Memory allocated to Cache
        videoSizeLambda (Callable): A function that take as input (idV, rng) and give as output the size of the video idV. In the function, you can use numpy as `np`, or `rng` to access a RandomState number generator initialised to the desired seed. 
        requestLambda (Callable): A function that take as input (idE, idV, rng) and give as output the count of the request (in this generator duplicated requests are not permitted). If the count is strictly below 1, then we consider the endpoint idE does not request the video idV. 
        dcLambda (Callable): A function that take as input (idE, rng) and give as output the latency to the datacenter for the corresponding endpoint idE.
        connectionLambda (Callable): A function that take as input (idE, idC, dcL, rng) and give as output the latency between an endpoint idE and the cache idC. If strictly below 1, we consider non connection exists. `dcL` is the latency to the corresponding data center. 
        seed (int, optional): A seed to use if `rng` is used in any of the user function. Defaults to 42.

    Returns:
        str: An instance
    """
    # Set up random number generator if requested
    rng = np.random.RandomState(seed)
    
    # Initialise ids to map
    idEs = np.arange(E)
    idVs = np.arange(V)
    idCs = np.arange(C)
    
    # Generate videos sizes (from idV)
    videos = list(map(lambda idV: videoSizeLambda(idV, rng), idVs))

    # Generate requests
    requests = {}
    for idE in idEs:
        requests[idE] = ([],[])
        for idV in idVs:
            # Get the number of occurrence requested from the endpoint and the video
            if (count := requestLambda(idE, idV, rng)) >= 1:
                requests[idE][0].append(idV)
                requests[idE][1].append(count)
        
        if len(requests[idE][0]) == 0:
            del requests[idE]
    
    # Generate dcLatency (from idE)
    dcLatencies = list(map(lambda idE: dcLambda(idE, rng), idEs))
    
    # Generate endpoint connections
    connections = {}
    for idE in idEs:
        connections[idE] = (dcLatencies[idE], [], [])
        for idC in idCs:
            # Get cache latencies and connections for idE, idC, maximal latency
            if (cache_latency := connectionLambda(idE, idC, dcLatencies[idE], rng)) >= 1:
                connections[idE][1].append(idC)
                connections[idE][2].append(cache_latency)
    
    return generatorToString(E, C, X, videos, requests, connections)
    
if __name__=="__main__":
    generateFrom:Literal["dejaVu", "universalLambda"] = "dejaVu"
    kwargs = {
        "E":115, # dejaVu + universalLambda
        "V":10_000, # dejaVu + universalLambda
        "R":999_000, # dejaVu
        "V_min_size":4, # dejaVu
        "V_max_size":110, # dejaVu
        "C":20, # dejaVu + universalLambda
        "X":2000, # dejaVu + universalLambda
        "seed":42, # dejaVu + universalLambda
        "videoSizeLambda": lambda idV, rng: max(1,MAX_AUTHORISED_VIDEO_SIZE - idV + rng.randint(0,idV+1)), # universalLambda
        "requestLambda": lambda idE, idV, rng: rng.randint(8000,12001) if (idE%2, idV%2) == (0,1) else rng.randint(-100,101), # universalLambda
        "dcLambda": lambda idE, rng: max(2,min((idE+MAX_AUTHORISED_SERVER_LATENCY)//2 + rng.randint(-100, 100), MAX_AUTHORISED_SERVER_LATENCY)), # universalLambda
        "connectionLambda": lambda idE, idC, dcL, rng: rng.randint(-300, min(MAX_AUTHORISED_CACHE_LATENCY, dcL-1)) # universalLambda
    }
        
    # Generate the instance
    with open(f"instances/custom_{generateFrom.lower()}{kwargs.get('seed', '')}.in", "w") as file:
        file.write(generator[generateFrom](**kwargs))
