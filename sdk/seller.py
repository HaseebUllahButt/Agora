from .agent import Agent

class Seller(Agent):
    """
    A specialized agent that lists and sells services on the Agora Marketplace.
    """
    def __init__(self, agent_id: str, service_name: str = None, service_type: str = "ai_task", price: float = 0.001, **kwargs):
        super().__init__(agent_id, **kwargs)
        self.service_name = service_name
        self.service_type = service_type
        self.price = price
        self.role = "merchant"
        self.task_handler = None

    def on_task(self, func):
        """Decorator to register a custom logic handler for this agent."""
        self.task_handler = func
        return func

    def set_service(self, name: str, description: str, price: float, service_type: str = None):
        """Configure the service being sold."""
        self.service_name = name
        self.description = description
        self.price = price
        if service_type:
            self.service_type = service_type
            
        self.register_service(
            name=name,
            service_type=self.service_type,
            description=description,
            price_usdc=price
        )
        print(f"✅ Service '{name}' [{self.service_type}] is now live for {price} USDC.")

    def serve(self, host: str = "0.0.0.0", port: int = 8001):
        """Start a local server to listen for tasks from the Agora Proxy."""
        import uvicorn
        from fastapi import FastAPI, Request
        
        app = FastAPI(title=f"Agora Agent: {self.id}")

        @app.post("/execute")
        async def execute_task(request: Request):
            payload = await request.json()
            if not self.task_handler:
                return {"status": "error", "message": "No task handler registered."}
            
            try:
                # Call the user's custom logic
                result = self.task_handler(payload)
                return {"status": "success", "data": result}
            except Exception as e:
                return {"status": "error", "message": str(e)}

        print(f"🚀 {self.id} is listening for tasks on port {port}...")
        uvicorn.run(app, host=host, port=port)
