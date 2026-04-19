import {
  initiateDeveloperControlledWalletsClient,
} from "@circle-fin/developer-controlled-wallets";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

async function main() {
  const apiKey = process.env.CIRCLE_API_KEY;
  const entitySecret = process.env.CIRCLE_ENTITY_SECRET;

  if (!apiKey || !entitySecret) {
    throw new Error("Missing CIRCLE_API_KEY or CIRCLE_ENTITY_SECRET in .env");
  }

  const client = initiateDeveloperControlledWalletsClient({
    apiKey,
    entitySecret,
  });

  const WALLET_SET_ID = "de6bdaa1-4c6a-58bb-90fc-8bb337d93080";

  const agentNames = [
    "web-search-agent",
    "summarizer-agent", 
    "extractor-agent",
    "formatter-agent",
  ];

  console.log("Creating 4 agent wallets...\n");

  const wallets: any[] = [];

  for (const name of agentNames) {
    const result = await client.createWallets({
      walletSetId: WALLET_SET_ID,
      blockchains: ["ARC-TESTNET"],
      count: 1,
      accountType: "EOA",
    });

    const wallet = result.data?.wallets?.[0];
    if (!wallet) throw new Error(`Failed to create wallet for ${name}`);

    console.log(`${name}`);
    console.log(`  ID:      ${wallet.id}`);
    console.log(`  Address: ${wallet.address}\n`);

    wallets.push({ name, id: wallet.id, address: wallet.address });
  }

  // Save to file
  fs.writeFileSync(
    path.join(__dirname, "output/agent-wallets.json"),
    JSON.stringify(wallets, null, 2),
    "utf-8"
  );

  // Append to .env
  const envPath = path.join(__dirname, ".env");
  for (const w of wallets) {
    const key = w.name.toUpperCase().replace(/-/g, "_");
    fs.appendFileSync(envPath, `${key}_ID=${w.id}\n`, "utf-8");
    fs.appendFileSync(envPath, `${key}_ADDRESS=${w.address}\n`, "utf-8");
  }

  console.log("All agent wallets created and saved to output/agent-wallets.json");
  console.log("Wallet IDs and addresses appended to .env");
}

main().catch((err) => {
  console.error("Error:", err.message || err);
  process.exit(1);
});
