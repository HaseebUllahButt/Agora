import {
  initiateDeveloperControlledWalletsClient,
  type TokenBlockchain,
} from "@circle-fin/developer-controlled-wallets";

const ARC_TESTNET_USDC = "0x3600000000000000000000000000000000000000";

const ORCHESTRATOR_ADDRESS = "0xfdbd8c61822158688b014226f2c6c7c2ecd9cd3f";

const AGENT_ADDRESSES = [
  { name: "web-search-agent",  address: "0xf55fb34df4e49d634ada464d5d1d9fcdd557bb8f" },
  { name: "summarizer-agent",  address: "0xc8a4b872e023b09db6b5fdeb6c61e586970804e6" },
  { name: "extractor-agent",   address: "0x312cbcfe78cdc4f2a5f272f7c695e9c07b5d5c32" },
  { name: "formatter-agent",   address: "0xdf160c1f3a1e1eb0a9d6c4b63ae638553445243f" },
];

async function main() {
  const apiKey = process.env.CIRCLE_API_KEY;
  const entitySecret = process.env.CIRCLE_ENTITY_SECRET;

  if (!apiKey || !entitySecret) {
    throw new Error("Missing API key or entity secret");
  }

  const client = initiateDeveloperControlledWalletsClient({
    apiKey,
    entitySecret,
  });

  for (const agent of AGENT_ADDRESSES) {
    console.log(`Funding ${agent.name}...`);

    const tx = await client.createTransaction({
      blockchain: "ARC-TESTNET" as TokenBlockchain,
      walletAddress: ORCHESTRATOR_ADDRESS,
      destinationAddress: agent.address,
      amount: ["2"],
      tokenAddress: ARC_TESTNET_USDC,
      fee: { type: "level", config: { feeLevel: "MEDIUM" } },
    });

    const txId = tx.data?.id;
    if (!txId) throw new Error(`Transaction failed for ${agent.name}`);

    // Poll for completion
    const terminalStates = new Set(["COMPLETE", "FAILED", "CANCELLED", "DENIED"]);
    let state = tx.data?.state;

    while (!state || !terminalStates.has(state)) {
      await new Promise((r) => setTimeout(r, 3000));
      const poll = await client.getTransaction({ id: txId });
      state = poll.data?.transaction?.state;
      console.log(`  state: ${state}`);
    }

    if (state === "COMPLETE") {
      console.log(`  ✓ ${agent.name} funded with 2 USDC\n`);
    } else {
      console.log(`  ✗ ${agent.name} failed: ${state}\n`);
    }
  }

  console.log("All agents funded. Ready to build Agora.");
}

main().catch((err) => {
  console.error("Error:", err.message || err);
  process.exit(1);
});
