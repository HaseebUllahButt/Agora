import os
from .agent import Agent

class Seller(Agent):
    """
    A specialized agent that lists and sells services on the Agora Marketplace.
    Can also act as a Buyer (Supply Chain) if given an operating budget.
    """
    def __init__(self, agent_id: str, service_name: str = None, service_type: str = "ai_task", price: float = 0.001, budget: float = 0.0, **kwargs):
        super().__init__(agent_id, **kwargs)
        self.service_name = service_name
        self.service_type = service_type
        self.price = price
        self.role = "merchant"
        self.task_handler = None
        
        self.budget = budget
        self.client = None
        
        # Dual-mode: If a budget is provided, this seller can ALSO buy things.
        if self.budget > 0:
            self._ensure_bootstrapped()
            if not self.circle_wallet_id:
                self.create_wallet()
            
            print(f"💰 Auto-funding Seller {self.id} with {self.budget} USDC operating budget...")
            self.fund(self.budget)
            self.client = self.create_client(self.budget)

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
            
    def publish(self):
        """Register the seller and its service on the marketplace."""
        print(f"🚀 Publishing {self.id} to Marketplace...")
        self.register()
        
        if self.service_name:
            self.register_service(
                name=self.service_name,
                service_type=self.service_type,
                description=getattr(self, "description", f"Service by {self.id}"),
                price_usdc=self.price
            )
            
            # Also register the task handler in the API's in-memory service registry
            # so the /purchase endpoint can execute it directly
            if self.task_handler:
                try:
                    from sdk.provider import get_service_registry
                    registry = get_service_registry()
                    # Match the provider_id format used by the DB
                    # The API looks up by the DB provider ID, so we need to register
                    # using the same ID that gets created in the providers table
                    from shared.core import get_db
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT id FROM providers WHERE agent_id = ? AND name = ? AND is_active = 1",
                            (self.id, self.service_name)
                        )
                        row = cursor.fetchone()
                        if row:
                            provider_id = row[0]
                            registry.register(
                                service_id=provider_id,
                                agent_id=self.id,
                                name=self.service_name,
                                func=self.task_handler,
                                price=self.price,
                                category=self.service_type,
                                description=getattr(self, "description", "")
                            )
                except Exception as e:
                    print(f"⚠️ Could not register handler in service registry: {e}")
            
            print(f"✅ Service '{self.service_name}' is live for {self.price} USDC!")
        else:
            print("⚠️ Profile created, but no service set. Use set_service().")

    def unpublish(self):
        """Temporarily remove the agent from the marketplace search."""
        self.set_status(active=False)
        print(f"⏸️ {self.id} has been unpublished.")

    def buy(self, seller_id: str, params: dict = None, service_name: str = None):
        """
        [Supply Chain] Allow the seller to buy a service from another agent.
        Requires an operating budget to have been set on init.
        """
        if not self.client:
            raise ValueError("Seller must be initialized with a budget > 0 to buy services.")
            
        print(f"🔄 [Supply Chain] {self.id} is hiring {seller_id}...")
        return self.client.buy_service(seller_id=seller_id, service_name=service_name, params=params)

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

        print(f"🎧 {self.id} is listening for tasks on port {port}...")
        uvicorn.run(app, host=host, port=port)
