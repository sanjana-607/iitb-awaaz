import json
import os
import unittest
from dotenv import load_dotenv

load_dotenv()

from app import app
import database as db

class GrievanceAppTestCase(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_01_public_feed(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"IITB Awaaz", response.data)
        self.assertIn(b"Non-functional Geyser in Hostel B", response.data)
        print("✓ Public feed page renders successfully with seeded posts")

    def test_02_submit_page(self):
        response = self.client.get('/submit')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Campus Grievance", response.data)
        print("✓ Voice submission page renders successfully")

    def test_03_admin_dashboard(self):
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Private Sensitive Queue", response.data)
        self.assertIn(b"Internal Complaints Committee", response.data)
        print("✓ Admin dashboard & private sensitive queue render successfully")

    def test_04_upvote(self):
        response = self.client.post('/api/upvote/1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertGreaterEqual(data['upvotes'], 15)
        print(f"✓ Upvoting working (New count: {data['upvotes']})")

    def test_05_status_update(self):
        response = self.client.post('/api/status/1', json={'status': 'Resolved'})
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], 'Resolved')
        print("✓ Status update working (Status changed to Resolved)")

    def test_06_api_submit_text(self):
        # Test submission through the Sarvam AI pipeline
        response = self.client.post('/api/submit', data={
            'text': 'Library ke 2nd floor pe AC kaam nahi kar raha, bahut garmi hai',
            'hostel': 'Hostel 3',
            'department': 'Mechanical Engineering',
            'batch': 'UG 2023',
            'anonymous': 'true'
        })
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.data)
        self.assertTrue(data['success'])
        self.assertIn('post', data)
        self.assertIn('title', data['post'])
        print(f"✓ Grievance submitted & structured: \"{data['post']['title']}\"")
        if data.get('audio_url'):
            print(f"✓ Bulbul confirmation audio generated: {data['audio_url']}")

if __name__ == '__main__':
    unittest.main()
