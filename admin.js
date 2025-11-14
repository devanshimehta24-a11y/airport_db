// Sidebar toggle
document.getElementById('toggleSidebar').addEventListener('click', function () {
  document.querySelector('aside').classList.toggle('hidden');
});

// Example data — these will come from Flask later
const flights = [
  { id: 'AI-204', from: 'BOM', to: 'DXB', dep: '09:20', status: 'Departed' },
  { id: '6E-101', from: 'BOM', to: 'DEL', dep: '10:15', status: 'On Time' },
  { id: 'SG-33', from: 'BOM', to: 'BLR', dep: '11:00', status: 'Delayed' }
];

const passengers = [
  { id: 102, name: 'Heena Shah', nat: 'Indian', age: 60, contact: '99287347' },
  { id: 103, name: 'Falguni Mehta', nat: 'Indian', age: 55, contact: '9082784196' },
  { id: 104, name: 'Faisal Khan', nat: 'Canadian', age: 34, contact: '889294376' }
];

// Render flights table
const flightsBody = document.getElementById('flightsBody');
flights.forEach(f => {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="p-2">${f.id}</td>
    <td>${f.from}</td>
    <td>${f.to}</td>
    <td>${f.dep}</td>
    <td>${f.status}</td>`;
  flightsBody.appendChild(tr);
});

// Render passengers table
const passengersBody = document.getElementById('passengersBody');
passengers.forEach(p => {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td class="p-2">${p.id}</td>
    <td>${p.name}</td>
    <td>${p.nat}</td>
    <td>${p.age}</td>
    <td>${p.contact}</td>`;
  passengersBody.appendChild(tr);
});

// Add button interactivity
document.getElementById('addFlight').addEventListener('click', () => {
  alert('Add Flight functionality coming soon!');
});

document.getElementById('addPassenger').addEventListener('click', () => {
  alert('Add Passenger functionality coming soon!');
});
