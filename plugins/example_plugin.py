# Example Edge Compute Plugin for EssaProxy

async def on_request(context: dict):
    """
    This function is dynamically executed by EssaProxy for every incoming request.
    You can modify the 'context' dictionary to change how the proxy handles the request.
    
    Context keys available:
    - client_ip (str)
    - header_data (bytes): The raw HTTP headers
    - drop (bool): Set to True to instantly drop the TCP connection
    - short_circuit_response (bytes): Set to a raw HTTP response to bypass the backend
    """
    header_data = context['header_data']
    headers_str = header_data.decode('utf-8', errors='ignore')
    
    # Example 1: Custom WAF / Firewall Rule
    # If the user tries to access a super-secret endpoint, drop them!
    if "GET /super-secret-edge" in headers_str:
        context['drop'] = True
        return
        
    # Example 2: Serverless Function (Short-circuit the backend)
    # If the user visits /ping, respond immediately from the Edge
    if "GET /ping " in headers_str:
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b'{"message": "pong from edge compute plugin!"}\n'
        )
        context['short_circuit_response'] = response
        return

    # Example 3: Header Mutation
    # Inject a custom tracking header before it hits the backend
    # We replace the ending \r\n\r\n with our header + \r\n\r\n
    if b'\r\n\r\n' in header_data:
        injected = header_data.replace(b'\r\n\r\n', b'\r\nX-Essa-Edge: injected-by-plugin\r\n\r\n', 1)
        context['header_data'] = injected
