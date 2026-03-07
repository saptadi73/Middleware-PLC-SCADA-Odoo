# Contoh Penggunaan: Update MO dengan Consumption by Equipment Code

## Overview

Endpoint `/api/scada/mo/update-with-consumptions` memungkinkan frontend untuk update Manufacturing Order dengan mengirimkan:
- Manufacturing Order ID
- Quantity produksi (optional)
- Consumption per equipment code (berdasarkan SCADA equipment code)

## Skenario Use Case

Berdasarkan screenshot yang diberikan, MO dengan ID `WH/MO/00001` memiliki komponen-komponen dengan equipment assignment:

| Product | SCADA Equipment | To Consume | Reserved | Consumed |
|---------|----------------|------------|----------|----------|
| Pollard Angsa | SILO A | 825.00 kg | 825.00 | 0.00 |
| Kopra mesh | SILO B | 375.00 kg | 375.00 | 0.00 |
| PKE Pellet | SILO C | 240.25 kg | 240.25 | 0.00 |
| Sawit | SILO D | 50.00 kg | 50.00 | 0.00 |
| Ddgs Corn | SILO E | 381.25 kg | 381.25 | 0.00 |
| ... | ... | ... | ... | ... |

## Request Format

### Frontend mengirim data seperti ini:

```javascript
const payload = {
  mo_id: "WH/MO/00001",
  quantity: 1985.5,     // Optional: Actual finished goods dari middleware, tanpa mark done
  silo101: 825,         // SILO A - Pollard Angsa
  silo102: 600,         // SILO B - Kopra mesh (misal ada perubahan dari 375 ke 600)
  silo103: 375,         // SILO C - PKE Pellet
  silo104: 50,          // SILO D - Sawit
  silo105: 381.25,      // SILO E - Ddgs Corn
  // ... equipment lainnya
};
```

**Catatan Penting:**
- Key harus menggunakan `equipment_code` yang terdaftar di master SCADA Equipment
- Format yang direkomendasikan di flow middleware: `silo101` ... `silo115`
- Alternatif yang juga didukung middleware: `scada_tag` seperti `silo_a`, `silo_b`, ..., `lq_tetes`, `lq_fml` (akan dikonversi ke equipment_code)
- `quantity` pada flow middleware ini diperlakukan sebagai actual finished goods, bukan target quantity MO
- Jika butuh rescale target MO, kirim field target yang eksplisit seperti `product_qty` atau `target_production`
- Value adalah consumption quantity dalam unit yang sesuai

## Contoh Implementasi

### 1. Vue.js dengan Axios

```javascript
// Service untuk update MO
import axios from 'axios';

const ODOO_BASE_URL = 'http://localhost:8069';

export const updateMOWithConsumptions = async (moId, quantity, consumptions) => {
  try {
    // Prepare payload
    const payload = {
      mo_id: moId,
    };
    
    // Add quantity if provided
    if (quantity !== null && quantity !== undefined) {
      payload.quantity = quantity;
    }
    
    // Add consumptions by equipment code
    Object.keys(consumptions).forEach(equipmentCode => {
      payload[equipmentCode] = consumptions[equipmentCode];
    });
    
    // Make API call
    const response = await axios.post(
      `${ODOO_BASE_URL}/api/scada/mo/update-with-consumptions`,
      payload,
      {
        headers: {
          'Content-Type': 'application/json',
        },
        withCredentials: true, // Important for session cookie
      }
    );
    
    return response.data;
  } catch (error) {
    console.error('Error updating MO:', error);
    throw error;
  }
};

// Usage example
const result = await updateMOWithConsumptions(
  'WH/MO/00001',
  2000,
  {
    'silo101': 825,
    'silo102': 600,
    'silo103': 375,
    'silo104': 50,
    'silo105': 381.25,
    'silo106': 250,
    'silo107': 62.50,
    'silo108': 83.50,
    'silo109': 83.25,
    'silo110': 83.25,
    'silo111': 3.75,
    'silo112': 0.25,
    'silo113': 42.00,
  }
);

console.log(result);
// Output:
// {
//   status: 'success',
//   message: 'MO updated successfully',
//   mo_id: 'WH/MO/00001',
//   mo_state: 'confirmed',
//   updated_finished_qty: 2000,
//   consumed_items: [...],
//   errors: []
// }
```

### 2. Vue.js Component Example

```vue
<template>
  <div class="mo-update-form">
    <h2>Update MO: {{ moId }}</h2>
    
    <div class="form-group">
      <label>Quantity to Produce:</label>
      <input v-model.number="quantity" type="number" step="0.01" />
    </div>
    
    <div class="components-section">
      <h3>Material Consumptions</h3>
      <div 
        v-for="component in components" 
        :key="component.equipmentCode"
        class="component-row"
      >
        <label>{{ component.name }} ({{ component.equipmentCode }}):</label>
        <input 
          v-model.number="consumptions[component.equipmentCode]" 
          type="number" 
          step="0.01"
          :placeholder="`Reserved: ${component.reserved}`"
        />
        <span class="unit">{{ component.uom }}</span>
      </div>
    </div>
    
    <button @click="submitUpdate" :disabled="loading">
      {{ loading ? 'Updating...' : 'Update MO' }}
    </button>
    
    <div v-if="result" class="result">
      <h4>Result:</h4>
      <pre>{{ JSON.stringify(result, null, 2) }}</pre>
    </div>
  </div>
</template>

<script>
import { updateMOWithConsumptions } from '@/services/scada-api';

export default {
  name: 'MOUpdateForm',
  
  data() {
    return {
      moId: 'WH/MO/00001',
      quantity: 2500,
      components: [
        { name: 'Pollard Angsa', equipmentCode: 'silo101', reserved: 825, uom: 'kg' },
        { name: 'Kopra mesh', equipmentCode: 'silo102', reserved: 375, uom: 'kg' },
        { name: 'PKE Pellet', equipmentCode: 'silo103', reserved: 240.25, uom: 'kg' },
        { name: 'Sawit', equipmentCode: 'silo104', reserved: 50, uom: 'kg' },
        { name: 'Ddgs Corn', equipmentCode: 'silo105', reserved: 381.25, uom: 'kg' },
        { name: 'Ampok Jagung', equipmentCode: 'silo106', reserved: 250, uom: 'kg' },
        { name: 'Kulit Kopi', equipmentCode: 'silo107', reserved: 62.50, uom: 'kg' },
        { name: 'Onggok', equipmentCode: 'silo108', reserved: 83.50, uom: 'kg' },
        { name: 'Tetes', equipmentCode: 'silo109', reserved: 83.25, uom: 'kg' },
        { name: 'Fml', equipmentCode: 'silo110', reserved: 83.25, uom: 'kg' },
        { name: 'Savemix', equipmentCode: 'silo111', reserved: 3.75, uom: 'kg' },
        { name: 'Demytox', equipmentCode: 'silo112', reserved: 0.25, uom: 'kg' },
        { name: 'CaCO3', equipmentCode: 'silo113', reserved: 42.00, uom: 'kg' },
      ],
      consumptions: {},
      loading: false,
      result: null,
    };
  },
  
  mounted() {
    // Initialize consumptions with reserved values
    this.components.forEach(comp => {
      this.consumptions[comp.equipmentCode] = comp.reserved;
    });
  },
  
  methods: {
    async submitUpdate() {
      this.loading = true;
      this.result = null;
      
      try {
        const result = await updateMOWithConsumptions(
          this.moId,
          this.quantity,
          this.consumptions
        );
        
        this.result = result;
        
        if (result.status === 'success') {
          this.$message.success('MO updated successfully!');
        } else {
          this.$message.error(result.message);
        }
      } catch (error) {
        this.$message.error('Failed to update MO: ' + error.message);
      } finally {
        this.loading = false;
      }
    },
  },
};
</script>

<style scoped>
.mo-update-form {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.component-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.component-row label {
  flex: 1;
}

.component-row input {
  width: 150px;
}

.unit {
  width: 50px;
  color: #666;
}

.result {
  margin-top: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 4px;
}
</style>
```

### 3. JavaScript/Fetch API Example

```javascript
async function updateMOConsumptions() {
  const payload = {
    mo_id: 'WH/MO/00001',
    quantity: 2500,
    'silo101': 825.00,
    'silo102': 375.00,
    'silo103': 240.25,
    'silo104': 50.00,
    'silo105': 381.25,
    'silo106': 250.00,
    'silo107': 62.50,
    'silo108': 83.50,
    'silo109': 83.25,
    'silo110': 83.25,
    'silo111': 3.75,
    'silo112': 0.25,
    'silo113': 42.00,
  };
  
  try {
    const response = await fetch(
      'http://localhost:8069/api/scada/mo/update-with-consumptions',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include', // Important for cookies
        body: JSON.stringify(payload),
      }
    );
    
    const result = await response.json();
    console.log('Update result:', result);
    
    if (result.status === 'success') {
      console.log(`✓ MO ${result.mo_id} updated successfully`);
      console.log(`  Updated finished qty: ${result.updated_finished_qty || 'N/A'}`);
      console.log(`  Consumed items: ${result.consumed_items.length}`);
      
      result.consumed_items.forEach(item => {
        console.log(`  - ${item.equipment_code}: ${item.applied_qty} (${item.products.join(', ')})`);
      });
      
      if (result.errors && result.errors.length > 0) {
        console.warn('  Errors:', result.errors);
      }
    } else {
      console.error('Failed to update MO:', result.message);
    }
    
    return result;
  } catch (error) {
    console.error('Error calling API:', error);
    throw error;
  }
}

// Call it
updateMOConsumptions();
```

### 4. Python Client Example

```python
import requests
import json

class ScadaClient:
    def __init__(self, base_url='http://localhost:8069', db='odoo14', login='admin', password='admin'):
        self.base_url = base_url
        self.session = requests.Session()
        self.authenticate(db, login, password)
    
    def authenticate(self, db, login, password):
        """Authenticate and get session cookie"""
        url = f'{self.base_url}/api/scada/authenticate'
        payload = {
            'db': db,
            'login': login,
            'password': password,
        }
        response = self.session.post(url, json=payload)
        result = response.json()
        
        if result.get('status') != 'success':
            raise Exception(f"Authentication failed: {result.get('message')}")
        
        print(f"✓ Authenticated as {login}")
        return result
    
    def update_mo_with_consumptions(self, mo_id, quantity=None, consumptions=None):
        """
        Update MO with quantity and consumptions by equipment code
        
        Args:
            mo_id: Manufacturing Order name (e.g., 'WH/MO/00001')
            quantity: Production quantity (optional)
            consumptions: Dict of equipment_code -> consumption_qty
        """
        url = f'{self.base_url}/api/scada/mo/update-with-consumptions'
        
        payload = {'mo_id': mo_id}
        
        if quantity is not None:
            payload['quantity'] = quantity
        
        if consumptions:
            payload.update(consumptions)
        
        response = self.session.post(url, json=payload)
        result = response.json()
        
        return result

# Usage
if __name__ == '__main__':
    client = ScadaClient(
        base_url='http://localhost:8069',
        db='odoo14',
        login='admin',
        password='admin'
    )
    
    # Update MO with consumptions
    result = client.update_mo_with_consumptions(
        mo_id='WH/MO/00001',
        quantity=2500,
        consumptions={
        'silo101': 825.00,
        'silo102': 375.00,
        'silo103': 240.25,
        'silo104': 50.00,
        'silo105': 381.25,
        'silo106': 250.00,
        'silo107': 62.50,
        'silo108': 83.50,
        'silo109': 83.25,
        'silo110': 83.25,
        'silo111': 3.75,
        'silo112': 0.25,
        'silo113': 42.00,
        }
    )
    
    print(json.dumps(result, indent=2))
```

## Response Examples

### Success Response

```json
{
  "status": "success",
  "message": "MO updated successfully",
  "mo_id": "WH/MO/00001",
  "mo_state": "confirmed",
  "updated_finished_qty": 2500,
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "equipment_name": "Main PLC - Injection Machine 01",
      "applied_qty": 825.0,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    },
    {
      "equipment_code": "silo102",
      "equipment_name": "SILO B Equipment",
      "applied_qty": 375.0,
      "move_ids": [124],
      "products": ["Kopra mesh"]
    }
  ],
  "errors": []
}
```

### Partial Success (dengan errors)

```json
{
  "status": "success",
  "message": "MO updated with some errors",
  "mo_id": "WH/MO/00001",
  "mo_state": "confirmed",
  "updated_finished_qty": 2500,
  "consumed_items": [
    {
      "equipment_code": "silo101",
      "equipment_name": "Main PLC - Injection Machine 01",
      "applied_qty": 825.0,
      "move_ids": [123],
      "products": ["Pollard Angsa"]
    }
  ],
  "errors": [
    "SILO_UNKNOWN: Equipment not found",
    "SILO_X: No raw material move found for this equipment"
  ]
}
```

### Error Response

```json
{
  "status": "error",
  "message": "Manufacturing Order \"WH/MO/99999\" not found"
}
```

## Setup Requirements

### 1. Equipment Master Setup

Pastikan setiap equipment sudah terdaftar dengan equipment_code yang benar:

```
Equipment Code: silo101
Name: Main PLC - Injection Machine 01
Type: Silo
...
```

### 2. BoM Line Setup

Setiap BoM line harus sudah di-assign ke equipment:

```
Product: Pollard Angsa
Quantity: 825.00 kg
SCADA Equipment: silo101
```

### 3. Stock Move Setup

Ketika MO dibuat, stock moves akan inherit equipment dari BoM line, sehingga bisa di-filter berdasarkan equipment code.

## Tips

1. **Equipment Code Consistency**: Pastikan equipment code yang dikirim dari frontend sama persis dengan yang ada di master data (case-sensitive).
  - Rekomendasi middleware: gunakan `silo101..silo115`.

2. **Handling Unknown Equipment**: Jika ada equipment code yang tidak ditemukan, akan masuk ke array `errors` di response, tapi proses tetap berlanjut untuk equipment lain yang valid.

3. **Overconsumption**: System membolehkan overconsumption (consume lebih dari quantity yang direncanakan). Jika ingin strict validation, bisa modify parameter `allow_overconsume=False`.

4. **Quantity Update**: Field `quantity` optional. Jika tidak ingin update quantity MO, cukup skip field tersebut.

5. **Transaction Safety**: Semua operasi dilakukan dalam satu transaction, jadi jika ada error fatal, semua changes akan di-rollback.

## Testing

```javascript
// Test dengan data minimal
const testPayload = {
  mo_id: 'WH/MO/00001',
  'silo101': 100,  // Test dengan satu equipment saja
};

// Test dengan update quantity
const testPayload2 = {
  mo_id: 'WH/MO/00001',
  quantity: 2500,
  'silo101': 100,
};

// Test dengan equipment tidak exist
const testPayload3 = {
  mo_id: 'WH/MO/00001',
  'silo999': 100,  // Should appear in errors
};
```
